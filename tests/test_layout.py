"""A DD-214 PDF read by where its blocks sit on the page.

The PDFs are fictional AUG 2009 forms that `synthetic_dd214.py` draws at test time, with
text in row-major order across the page so blocks 11/12 and 13/14 interleave the way a
scanned form's OCR layer does. Expected values come from what the generator draws.
"""

import importlib.util
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest
import synthetic_dd214 as form
from reportlab.pdfgen.canvas import Canvas

from dd214kw.cli import main
from dd214kw.evidence import SourceFactory
from dd214kw.extract import Content, load_text
from dd214kw.extractors import Dd214, read
from dd214kw.extractors.dd214_layout import NOT_READ
from dd214kw.index import DEFAULT_INDEX
from dd214kw.models import Duration
from dd214kw.resolve import resolve

FIX = Path(__file__).parent / "fixtures"
SPECIALTIES = [("35M20 HUMAN INTELLIGENCE COLLECTOR", 99), ("35F10 INTELLIGENCE ANALYST", 48)]
AWARDS = [
    ("ARMY COMMENDATION MEDAL", 2),
    ("ARMY ACHIEVEMENT MEDAL", 3),
    ("ARMY GOOD CONDUCT MEDAL", 4),
    ("NATIONAL DEFENSE SERVICE MEDAL", 1),
    ("GLOBAL WAR ON TERRORISM SERVICE MEDAL", 1),
    ("ARMY SERVICE RIBBON", 1),
    ("OVERSEAS SERVICE RIBBON", 2),
]
COURSES = [("BASIC LEADER COURSE", 4.0, 2012), ("ADVANCED LEADER COURSE", 6.0, 2016)]
NET_ACTIVE, FOREIGN = Duration(12, 3, 15), Duration(1, 4, 11)

needs_tesseract = pytest.mark.skipif(
    not form.tools_available(), reason="needs the tesseract and pdftoppm binaries"
)
needs_ocr_extra = pytest.mark.skipif(
    not (importlib.util.find_spec("pytesseract") and importlib.util.find_spec("pdf2image")),
    reason="needs the 'ocr' extra: uv sync --extra ocr",
)


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("dd214")


@pytest.fixture(scope="module")
def clean_pdf(pdfs):
    return form.write_text_pdf(pdfs / "clean.pdf")


@pytest.fixture(scope="module")
def noisy_pdf(pdfs):
    return form.write_text_pdf(pdfs / "noisy.pdf", noisy=True)


@pytest.fixture(scope="module")
def scan_png(pdfs, clean_pdf):
    if not form.tools_available():
        pytest.skip("needs the tesseract and pdftoppm binaries")
    return form.rasterize(clean_pdf, pdfs / "scan.png")


@pytest.fixture(scope="module")
def ocr_pdf(pdfs, scan_png):
    """The scan with tesseract's text layer: real OCR coordinates and real OCR noise."""
    return form.write_ocr_pdf(scan_png, pdfs / "ocr.pdf")


@pytest.fixture(scope="module")
def image_pdf(pdfs, scan_png):
    """The scan alone, with no text layer: `--ocr` has to read it."""
    return form.write_image_pdf(scan_png, pdfs / "image.pdf")


def _line_order(pdf: Path):
    """The PDF read the way main read it: its text in line order, without word positions."""
    return Dd214().extract(Content(load_text(pdf).text), SourceFactory.for_bytes(pdf.read_bytes()))


def _occupations(profile):
    return [(o.value.title, o.value.months) for o in profile.occupations]


def test_words_in_one_text_run_keep_their_own_positions(noisy_pdf):
    """The noisy form writes block 11's first line and row 12a's label as one text run."""
    words = {w.text: w for w in load_text(noisy_pdf).words}
    assert words["COLLECTOR"].x1 < form.GRID_X0 < words["ENTERED"].x0


def test_line_order_mixes_side_by_side_blocks(noisy_pdf):
    """The reported failure, and the same PDF read by position."""
    _, facts = _line_order(noisy_pdf)
    before = resolve(facts)
    assert before.context.branch is None
    assert "net_active" not in before.service_time
    assert any("DATE ENTERED AD THIS PERIOD" in title for title, _ in _occupations(before))
    assert before.training == ()

    after = resolve(read(noisy_pdf)[1])
    assert after.context.branch == "Army"
    assert after.service_time["net_active"] == NET_ACTIVE
    assert _occupations(after) == SPECIALTIES


@pytest.mark.parametrize(
    "variant", ["clean_pdf", "noisy_pdf", pytest.param("ocr_pdf", marks=needs_tesseract)]
)
def test_each_block_is_read_from_its_own_box(variant, request):
    doc, facts = read(request.getfixturevalue(variant))
    profile = resolve(facts)
    assert doc.layout == "2000"
    ctx = profile.context
    assert (ctx.branch, ctx.rank, ctx.pay_grade, ctx.as_of) == (
        "Army",
        "SSG",
        "E6",
        date(2020, 10, 3),
    )
    assert _occupations(profile) == SPECIALTIES  # no block 12 text, no "0000" or "2008" codes
    assert profile.service_time["net_active"] == NET_ACTIVE
    assert profile.service_time["foreign"] == FOREIGN
    assert [(a.value.name, a.value.count) for a in profile.awards] == AWARDS
    assert [
        (t.value.title, t.value.weeks, t.value.completed.year) for t in profile.training
    ] == COURSES


def test_unreadable_cells_are_left_out_not_guessed(noisy_pdf):
    """Block 12d's day reads 80 and 12g's month 0B: neither is a value, so neither is used."""
    doc, facts = read(noisy_pdf)
    profile = resolve(facts)
    assert "prior_active" not in profile.service_time
    assert "sea" not in profile.service_time
    assert [n for n in doc.notes if "12d" in n or "12g" in n] == [
        "The value of block 12d (total prior active service) could not be read; not used.",
        "The value of block 12g (sea service) could not be read; not used.",
    ]


@pytest.mark.parametrize(
    "variant", ["clean_pdf", "noisy_pdf", pytest.param("ocr_pdf", marks=needs_tesseract)]
)
def test_personal_blocks_never_reach_facts_or_report(variant, request, capsys):
    pdf = request.getfixturevalue(variant)
    doc, facts = read(pdf)
    outputs = [json.dumps([asdict(doc), *map(asdict, facts), asdict(resolve(facts))], default=str)]
    if DEFAULT_INDEX.exists():
        assert main(["translate", str(pdf), "-f", "json"]) == 0
        outputs.append(capsys.readouterr().out)
    for out in outputs:
        leaked = [v for v in form.SENSITIVE.values() if v.upper() in out.upper()]
        assert leaked == []


def test_page_set_out_one_block_per_line_reads_as_before(tmp_path):
    """Line order is block order here, so the layout reader leaves the page alone."""
    pdf = tmp_path / "dd214.pdf"
    c = Canvas(str(pdf))
    y = 800
    for line in (FIX / "army_2000.txt").read_text().splitlines():
        c.drawString(20, y, line[:110])
        y -= 12
        if y < 40:
            c.showPage()
            y = 800
    c.save()
    assert read(pdf) == _line_order(pdf)


def test_2022_edition_is_read_in_line_order_as_before(tmp_path):
    pdf = form.write_text_pdf(tmp_path / "dd214.pdf", title="CERTIFICATE OF UNIFORMED SERVICE")
    assert read(pdf) == _line_order(pdf)


def test_page_without_block_labels_is_read_in_line_order_with_a_note(tmp_path):
    pdf = tmp_path / "dd214.pdf"
    c = Canvas(str(pdf))
    lines = [
        form.TITLE,
        "A TRANSCRIPT OF THE FORM, WITHOUT ITS NUMBERED BLOCK LABELS",
        "PRIMARY SPECIALTY",
        "11B10 INFANTRYMAN 2 YRS 0 MOS",
    ]
    for i, line in enumerate(lines):
        c.drawString(40, 760 - 14 * i, line)
    c.save()
    doc, facts = read(pdf)
    assert NOT_READ in doc.notes
    assert [title for title, _ in _occupations(resolve(facts))] == ["11B10 INFANTRYMAN"]


@needs_ocr_extra
def test_scan_without_text_layer_is_read_by_position_with_ocr(image_pdf):
    doc, facts = read(image_pdf, ocr=True)
    profile = resolve(facts)
    assert (profile.context.branch, profile.context.pay_grade) == ("Army", "E6")
    assert _occupations(profile) == SPECIALTIES
    assert profile.service_time["net_active"] == NET_ACTIVE
    assert [(a.value.name, a.value.count) for a in profile.awards] == AWARDS
    # OCR may misread a cell; the reader then leaves it out with a note, never a guess.
    if "foreign" in profile.service_time:
        assert profile.service_time["foreign"] == FOREIGN
    else:
        assert any("12f" in n for n in doc.notes)
