"""`dd214kw inspect-layout` prints a DD-214 page's geometry and nothing from the document.

The PDFs are the fictional forms `synthetic_dd214.py` draws, filled in with fake personal
values. Privacy is checked two ways. Structurally, every output line after the fixed
header matches a strict grammar whose only free fields are our own ids, counts, scores and
coordinates. As a denylist, no token of a drawn value appears. The picture is checked for
the calls that drew it and for the colours it holds.
"""

import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
import synthetic_dd214 as form
from PIL import Image, ImageDraw

from dd214kw.cli import main
from dd214kw.extractors.dd214_layout import EDITION_2000
from dd214kw.inspect_layout import HEADER, LABEL_IDS, PALETTE, inspect, report, write_png

BLOCKS = {*EDITION_2000.written, *EDITION_2000.withheld} - {EDITION_2000.record}
TAGS = {*LABEL_IDS, *(f"B{block}" for block in BLOCKS)}

N = r"-?\d{1,4}\.\d"  # a coordinate to 0.1: no run of five digits, such as a date, fits
BOX = " ".join([N] * 4)
SHAPE = r"[DAMP]\d{1,3}"
PAGE = r"page \d{1,2}"
GRAMMAR = tuple(
    re.compile(rule)
    for rule in (
        r"source (text-layer|ocr)",
        r"pages \d{1,2}",
        rf"{PAGE} size {N} {N} unit (pt|px)",
        r"\[(labels|words|runs|rules|reader)\]",
        rf"label (?P<label>\w+) {PAGE} score \d{{1,3}}\.\d bbox {BOX}",
        rf"missing (?P<label>\w+) {PAGE}",
        rf"line \d{{1,4}} {PAGE}( \| {BOX} {SHAPE})+",
        rf"run {PAGE} bbox {BOX} words \d{{1,4}} crosses \d{{1,3}}",
        rf"rules {PAGE} source (drawn|image|absent) count \d{{1,4}}",
        rf"rule {PAGE} [hv] {BOX}",
        rf"reader (line-order|position {PAGE})",
        rf"block B(?P<block>\w+) status (read|refused|not-found|withheld)( bbox {BOX})?",
        rf"cell B12[a-i] (yr|mo|dy) status (read|refused|not-found)"
        rf"( bbox {BOX} words \d{{1,2}}( shape {SHAPE})?)?",
        rf"cell B12[a-i] (yr|mo|dy) reread crop {BOX} zoom \d\.\d shape ({SHAPE}|none)"
        rf" (accepted|refused)",
    )
)
VALUE_TOKENS = {
    token for value in form.values() for token in re.findall(r"[A-Z0-9]+", value.upper())
}
VALUE_TOKENS = {token for token in VALUE_TOKENS if len(token) >= 2}

needs_tesseract = pytest.mark.skipif(
    not form.tools_available(), reason="needs the tesseract and pdftoppm binaries"
)
needs_ocr_extra = pytest.mark.skipif(
    not (importlib.util.find_spec("pytesseract") and importlib.util.find_spec("pdf2image")),
    reason="needs the 'ocr' extra: uv sync --extra ocr",
)


@dataclass(frozen=True)
class Variant:
    name: str
    pdf: Path
    ocr: bool  # a scan with no text layer, read with --ocr


@pytest.fixture(scope="module")
def scan_png(tmp_path_factory) -> Path:
    if not form.tools_available():
        pytest.skip("needs the tesseract and pdftoppm binaries")
    d = tmp_path_factory.mktemp("scan")
    return form.rasterize(form.write_text_pdf(d / "clean.pdf"), d / "scan.png")


@pytest.fixture(
    scope="module",
    params=[
        "clean",
        "noisy",
        "overlap",
        pytest.param("ocr", marks=needs_tesseract),
        pytest.param("scan", marks=[needs_tesseract, needs_ocr_extra]),
        pytest.param("scan-text", marks=[needs_tesseract, needs_ocr_extra]),
    ],
)
def variant(request, tmp_path_factory) -> Variant:
    pdf = tmp_path_factory.mktemp(request.param) / "dd214.pdf"
    match request.param:
        case "clean":
            form.write_text_pdf(pdf)
        case "noisy":
            form.write_text_pdf(pdf, noisy=True)
        case "overlap":
            form.write_text_pdf(pdf, overlap=True)
        case "ocr":
            form.write_ocr_pdf(request.getfixturevalue("scan_png"), pdf)
        case "scan":
            form.write_image_pdf(request.getfixturevalue("scan_png"), pdf)
        case "scan-text":
            form.write_scan_pdf(request.getfixturevalue("scan_png"), pdf)
    return Variant(request.param, pdf, request.param == "scan")


@pytest.fixture(scope="module")
def inspected(variant, tmp_path_factory) -> tuple[list[str], Path]:
    """inspect-layout run on the variant the way the user runs it: its text, its picture."""
    out = tmp_path_factory.mktemp("out")
    txt, png = out / "layout.txt", out / "layout.png"
    argv = ["inspect-layout", str(variant.pdf), "-o", str(txt), "--png", str(png)]
    assert main([*argv, *(["--ocr"] if variant.ocr else [])]) == 0
    return txt.read_text(encoding="utf-8").splitlines(), png


def test_every_line_is_the_fixed_header_or_geometry(inspected):
    lines, _ = inspected
    assert lines[: len(HEADER)] == list(HEADER)
    for line in lines[len(HEADER) :]:
        match = next((m for rule in GRAMMAR if (m := rule.fullmatch(line))), None)
        assert match, f"not in the grammar: {line}"
        ids = match.groupdict()
        assert ids.get("label", LABEL_IDS[0]) in LABEL_IDS
        assert ids.get("block", "2") in BLOCKS


def test_no_token_of_a_drawn_value_appears(inspected):
    """The header is left out: it is the module's fixed text, checked above, and says "no
    text from your document". Tokens of digits alone are left to the grammar, which allows
    digits only in ids, counts, scores and coordinates: an x of 456.0 is no leak of the
    456 in an address."""
    lines, _ = inspected
    tokens = {t.upper() for line in lines[len(HEADER) :] for t in re.findall(r"\w+", line)}
    assert {t for t in tokens if not t.isdigit()} & VALUE_TOKENS == set()


def test_picture_holds_only_the_shapes_colours(inspected):
    """A scan pasted in would bring its greys: the picture would hold more colours."""
    _, png = inspected
    with Image.open(png) as img:
        colours = img.convert("RGB").getcolors(maxcolors=len(PALETTE))
    assert colours is not None
    assert {colour for _, colour in colours} <= set(PALETTE.values())


def test_picture_is_drawn_from_boxes_lines_and_our_ids_alone(variant, monkeypatch, tmp_path):
    result = inspect(variant.pdf, ocr=variant.ocr)
    calls: list[tuple[str, tuple]] = []
    real_draw = ImageDraw.Draw

    class Recorder:
        def __init__(self, draw):
            self._draw = draw

        def __getattr__(self, name):
            def call(*args, **kwargs):
                calls.append((name, args))
                return getattr(self._draw, name)(*args, **kwargs)

            return call

    def forbidden(*args, **kwargs):
        raise AssertionError("an image was put on the canvas")

    monkeypatch.setattr(ImageDraw, "Draw", lambda img, mode=None: Recorder(real_draw(img, mode)))
    for owner, name in (
        (Image.Image, "paste"),
        (Image.Image, "alpha_composite"),
        (Image, "alpha_composite"),
        (Image, "composite"),
        (Image, "blend"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    write_png(result, tmp_path / "layout.png")

    assert {name for name, _ in calls} <= {"rectangle", "line", "text"}
    tags = {args[1] for name, args in calls if name == "text"}
    assert tags
    assert tags <= TAGS


def test_inspection_finds_the_form_and_what_the_reader_did(variant, inspected):
    lines, _ = inspected
    text = "\n".join(lines)
    source, unit, rules = {
        "clean": ("text-layer", "pt", "drawn"),
        "noisy": ("text-layer", "pt", "drawn"),
        "overlap": ("text-layer", "pt", "drawn"),
        "ocr": ("text-layer", "pt", "image"),
        "scan": ("ocr", "px", "image"),
        "scan-text": ("text-layer", "pt", "image"),
    }[variant.name]
    assert f"source {source}" in lines
    assert re.search(rf"^page 0 size {N} {N} unit {unit}$", text, re.M)
    assert re.search(rf"^rules page 0 source {rules} count [1-9]\d*$", text, re.M)
    found = set(re.findall(r"^label (\w+) ", text, re.M))
    assert {"L4a", "L4b", "L5", "L7a", "L11", "L12", "L13", "L14", "L12a", "L12yr"} <= found
    assert set(re.findall(r"^missing (\w+) ", text, re.M)) == set(LABEL_IDS) - found
    assert "reader position page 0" in lines
    statuses = dict(re.findall(r"^block B(\w+) status ([\w-]+)", text, re.M))
    written = set(EDITION_2000.written) - {EDITION_2000.record}
    assert {b for b, s in statuses.items() if s == "read"} == written


@pytest.mark.parametrize("overlap", [False, True])
def test_form_shows_every_label_and_each_block_12_cell(overlap, tmp_path):
    """With the rows overlapping too: that form is what the reader was refusing to read."""
    lines = report(inspect(form.write_text_pdf(tmp_path / "dd214.pdf", overlap=overlap)))
    found = {line.split()[1] for line in lines if line.startswith("label ")}
    assert set(LABEL_IDS) - found == {"Lspecial"}  # the synthetic form does not print it
    cells = [line for line in lines if line.startswith("cell ")]
    assert len(cells) == 27
    assert all(" status read bbox " in cell for cell in cells)


def test_noisy_form_shows_the_cells_the_reader_refused(tmp_path):
    lines = report(inspect(form.write_text_pdf(tmp_path / "dd214.pdf", noisy=True)))
    rows = dict(re.findall(r"^cell B12(\w) yr status ([\w-]+)", "\n".join(lines), re.M))
    assert rows == {row: "refused" if row in "dg" else "read" for row in "abcdefghi"}


@needs_tesseract
@needs_ocr_extra
def test_output_shows_what_came_back_when_a_cell_was_read_again(scan_png, tmp_path):
    """Block 12c's years are garbled in this text layer, so the reader cuts that cell out
    of the page image and reads it again. The report shows the crop, how far it was
    enlarged, and the shape of what came back, so a failing cell can be diagnosed without
    anyone seeing its digits."""
    pdf = form.write_scan_pdf(scan_png, tmp_path / "scan-text.pdf")
    lines = [line for line in report(inspect(pdf)) if " reread " in line]
    assert any(line.startswith("cell B12c yr reread crop ") for line in lines)
    assert any(line.endswith(" accepted") for line in lines)


def test_output_shows_a_block_refused_for_a_lost_label(tmp_path):
    lines = report(inspect(form.write_text_pdf(tmp_path / "dd214.pdf", omit=("7a", "7b"))))
    assert {"missing L7a page 0", "missing L7b page 0"} <= set(lines)
    refused = {line.split()[1] for line in lines if re.match(r"block \w+ status refused ", line)}
    assert refused == {"B4a", "B4b"}
