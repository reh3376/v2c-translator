"""A DD-214 PDF read by where its blocks sit on the page.

The PDFs are fictional AUG 2009 forms that `synthetic_dd214.py` draws at test time, with
text in row-major order across the page so blocks 11/12 and 13/14 interleave the way a
scanned form's OCR layer does. Expected values come from what the generator draws.
"""

import importlib.util
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest
import synthetic_dd214 as form
from reportlab.pdfgen.canvas import Canvas

from dd214kw.cli import main
from dd214kw.evidence import SourceFactory
from dd214kw.extract import Content, OcrToolError, load_text
from dd214kw.extractors import Dd214, read
from dd214kw.extractors.dd214_layout import (
    NOT_READ,
    OCR_TOOLS_FAILED,
    OCR_TOOLS_MISSING,
    Status,
    read_form,
)
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
def overlap_pdf(pdfs):
    """The form as the user's scanner left it: every value on its printed label's own line,
    block 12's row labels off the values they name, and blocks 13 and 14's labels sharing a
    line. See `synthetic_dd214.OVERLAP_SHIFT`."""
    return form.write_text_pdf(pdfs / "overlap.pdf", overlap=True)


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


@pytest.fixture(scope="module")
def drifted_pdf(pdfs, clean_pdf):
    """A scan of 150 dpi, as a plain office scanner makes, whose text layer boxes block
    12b's values below the row they sit in on the page, so a crop of each of those cells
    spans the ruled line under that row, and garbles them. See `form.DRIFTED_CELLS`."""
    if not form.tools_available():
        pytest.skip("needs the tesseract and pdftoppm binaries")
    png = form.rasterize(clean_pdf, pdfs / "scan-150.png", dpi=150)
    return form.write_scan_pdf(
        png, pdfs / "drifted.pdf", cells=form.DRIFTED_CELLS, cell_drift=form.CELL_DRIFT
    )


@pytest.fixture(scope="module")
def scan_text_pdf(pdfs, scan_png):
    """The scan's image with a text layer over it, as a scanner's own PDF holds both, and
    with block 12c's years garbled in the text layer alone."""
    return form.write_scan_pdf(scan_png, pdfs / "scan-text.pdf")


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
    "variant",
    ["clean_pdf", "noisy_pdf", "overlap_pdf", pytest.param("ocr_pdf", marks=needs_tesseract)],
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


def test_rows_that_overlap_their_labels_are_still_read_whole(overlap_pdf):
    """The reported failure on a real form: the printed labels and the typed values share
    lines, so no label read whole, blocks grew over their neighbours and block 12's rows
    came out one row off. Read by position, the page still gives up every block."""
    layout = read_form(*_loaded(overlap_pdf)).layout
    read = {r.block for r in layout.regions if r.status is Status.READ}
    assert read == {"2", "4a", "4b", "11", "13", "14"}
    assert len(layout.cells) == 27
    assert {c.status for c in layout.cells} == {Status.READ}


def test_block_12_rows_come_from_the_columns_not_the_row_labels(overlap_pdf):
    """Block 12f's label sits beside row g's value on this form. Boxed from the label, the
    reader took the zeroes of row g for the foreign service of row f."""
    profile = resolve(read(overlap_pdf)[1])
    assert profile.service_time["foreign"] == FOREIGN
    assert profile.service_time["net_active"] == NET_ACTIVE
    assert profile.service_time["sea"] == Duration(0, 0, 0)


@needs_tesseract
@needs_ocr_extra
def test_a_cell_the_text_layer_garbled_is_read_again_from_the_page(scan_text_pdf):
    """The scan behind the text layer still shows block 12c's years. A row the text layer
    lost is read off the image, which is where the user's net active service went."""
    doc, facts = read(scan_text_pdf)
    assert resolve(facts).service_time["net_active"] == NET_ACTIVE
    assert [n for n in doc.notes if "12c" in n] == []


def test_zero_look_alikes_in_a_block_12_cell_read_as_zeros(tmp_path):
    """The shapes the user's own text layer left in block 12: a zero read as "()", "Q" or
    "D", and "00" read as "NO". A row of zeros is a value the form prints, so a row left in
    these shapes must read as zero rather than as a row that could not be read."""
    pdf = form.write_text_pdf(
        tmp_path / "dd214.pdf",
        cells={
            ("d", 0): "0O0D",
            ("d", 1): "NO",
            ("d", 2): "QO",
            ("e", 0): "0Q0O",
            ("e", 1): "()()",
            ("e", 2): "D0",
        },
    )
    doc, facts = read(pdf)
    assert resolve(facts).service_time["prior_active"] == Duration(0, 0, 0)
    assert [n for n in doc.notes if "12d" in n or "12e" in n] == []


@needs_tesseract
@needs_ocr_extra
def test_a_cell_against_a_ruled_line_is_read_from_the_page(drifted_pdf):
    """The reported failure on the user's form: re-reading a block 12 cell came back with
    nothing at all. The cell sits against the rule under its row, and tesseract reads a
    crop with a line across it as nothing, so the line is whitened before the crop is read.
    The separation date is what went missing with the row."""
    doc, facts = read(drifted_pdf)
    assert resolve(facts).context.as_of == date(2020, 10, 3)
    assert [n for n in doc.notes if "12b" in n] == []
    assert {c.status for c in read_form(*_loaded(drifted_pdf)).layout.cells} == {Status.READ}


def test_a_length_of_service_of_zeros_in_cells_of_the_wrong_length_reads_as_zero(tmp_path):
    """Block 12g as the user's text layer left block 12e: every cell holds zeros read as
    brackets or letters, and none of them holds as many characters as the form prints
    digits. No other value can read like that, so the row is no service rather than a row
    that could not be read; the cells are not re-read off the page, and nothing is guessed.
    """
    pdf = form.write_text_pdf(
        tmp_path / "dd214.pdf", cells={("g", 0): "()()", ("g", 1): "OOO", ("g", 2): "()"}
    )
    doc, facts = read(pdf)
    assert resolve(facts).service_time["sea"] == Duration(0, 0, 0)
    assert [n for n in doc.notes if "12g" in n] == []


def test_a_date_whose_year_no_one_served_in_is_not_a_date(tmp_path):
    """Repairing a cell can make digits that read as a date and are still a misread: "()()"
    for "20" leaves block 12b in the year 20. A row like that is refused, not used."""
    pdf = form.write_text_pdf(tmp_path / "dd214.pdf", cells={("b", 0): "()()20"})
    doc, facts = read(pdf)
    assert resolve(facts).context.as_of is None
    assert [n for n in doc.notes if n.startswith("The value of block 12b")] == [
        "The value of block 12b (separation date this period) could not be read; not used."
    ]


@needs_tesseract
@needs_ocr_extra
def test_a_cell_with_no_words_at_all_is_read_from_the_page(scan_png, tmp_path):
    """Block 12d's days are missing from the user's text layer altogether. The row's other
    cells still say where that cell sits, so it is cut from the page image and read."""
    pdf = form.write_scan_pdf(scan_png, tmp_path / "scan-text.pdf", cells={("d", 2): ""})
    doc, facts = read(pdf)
    assert resolve(facts).service_time["prior_active"] == Duration(0, 0, 0)
    assert [n for n in doc.notes if "12d" in n] == []


@needs_tesseract
@needs_ocr_extra
def test_a_cell_the_ocr_tools_cannot_re_read_says_what_would_read_it(scan_text_pdf, monkeypatch):
    """Without the OCR tools there is no second reading of a cell the text layer garbled.
    The note says why once, and what to install, instead of only that a value was not
    used."""
    monkeypatch.setitem(sys.modules, "pytesseract", None)
    doc, facts = read(scan_text_pdf)
    assert "net_active" not in resolve(facts).service_time
    assert [n for n in doc.notes if n == OCR_TOOLS_MISSING] == [OCR_TOOLS_MISSING]


@needs_tesseract
@needs_ocr_extra
def test_a_cell_nothing_could_re_read_is_not_called_unreadable(scan_text_pdf, monkeypatch):
    """The hosted container's root filesystem is read-only, so the OCR tools can be
    installed and still have nowhere to write the temporary file they work through. A cell
    nothing ever read is not a cell that could not be read: saying it was sends a veteran
    back to their scanner over a fault on this machine. One note, naming the error's class
    and nothing else."""
    import pytesseract

    def no_temp_directory(*args, **kwargs):
        raise PermissionError(30, "Read-only file system")

    monkeypatch.setattr(pytesseract, "image_to_string", no_temp_directory)
    doc, facts = read(scan_text_pdf)

    assert "net_active" not in resolve(facts).service_time
    assert [n for n in doc.notes if "could not be read" in n] == []
    assert [n for n in doc.notes if n.startswith("The OCR tools on this machine")] == [
        OCR_TOOLS_FAILED.format(kind="PermissionError")
    ]


@needs_tesseract
@needs_ocr_extra
def test_a_scan_the_ocr_tools_could_not_run_on_is_not_a_bad_document(image_pdf, monkeypatch):
    """A page with no text layer is nothing but OCR, so there is no report to put a note
    on: the CLI says `ocr-unavailable: <class>` and exits 3, which the hosted route turns
    into "this server could not read a scanned page" and not "your file is unreadable"."""
    import pytesseract

    def no_temp_directory(*args, **kwargs):
        raise PermissionError(30, "Read-only file system")

    monkeypatch.setattr(pytesseract, "image_to_data", no_temp_directory)
    with pytest.raises(OcrToolError) as raised:
        read(image_pdf, ocr=True)
    assert raised.value.kind == "PermissionError"

    assert main(["translate", str(image_pdf), "--ocr", "-f", "json"]) == 3


def test_a_net_active_service_the_dates_contradict_is_noted_not_corrected(tmp_path):
    """Block 12c is the time between 12a and 12b, counted inclusively. Time lost (block 29)
    is withheld, so a figure that does not follow from the dates is reported, not changed."""
    pdf = form.write_text_pdf(tmp_path / "dd214.pdf", cells={("c", 2): "29"})
    doc, facts = read(pdf)
    assert resolve(facts).service_time["net_active"] == Duration(12, 3, 29)
    assert [n for n in doc.notes if n.startswith("Block 12c")] == [
        "Block 12c (net active service this period) is 14 days longer than the period "
        "between the dates in 12a and 12b; the form's own figure is used (time lost is "
        "not read)."
    ]


def test_an_entry_split_across_lines_stays_one_entry(tmp_path):
    """Block 11's entries are separated by "//", which OCR may write as "/ /", and the box
    wraps them. An entry that wraps must not become two, or a specialty loses its months."""
    pdf = form.write_text_pdf(
        tmp_path / "dd214.pdf",
        blocks={
            "11": "35M20 HUMAN INTELLIGENCE COLLECTOR 8 YRS 3 MOS / / "
            "35F10 INTELLIGENCE ANALYST 4 YRS 0 MOS / / NOTHING FOLLOWS"
        },
    )
    assert _occupations(resolve(read(pdf)[1])) == SPECIALTIES


# Block 11's printed label as a scanner's OCR left it, its last words garbled. The typed
# value sits on this line too (see the overlap fixture), so the label's tail runs into the
# first entry's title.
GARBLED_LABEL_11 = (
    "11. PRIMARY SPECIALTY (List number, title and years and months in specialty. List\n"
    "additional specialty numbers and titles involving periods of\nONE OR MO,E S/RS!"
)
# One entry wrapping between its years and its months, an entry separator OCR read as
# "I I", and a misread "NOTHING FOLLOWS". The codes, titles and times are invented.
WRAPPED_SPECIALTIES = (
    "25U60 2B SI GI NT SGT/ CHIEF - 11 YRS\n"
    "2 MOS I I 25B4L NETWORK SYSTEMS OPERATOR - 23 YRS 5 MOS I I NOTHTNG FOLLOWS"
)


def test_block_11s_wrapped_label_does_not_reach_the_first_specialty(tmp_path):
    """The reported failure. The end of block 11's printed label came out as part of the
    first entry's title; the entry wrapped between "11 YRS" and "2 MOS", so its months
    began the next entry's title instead of counting; and "NOTHING FOLLOWS" became an
    entry of its own."""
    pdf = form.write_text_pdf(
        tmp_path / "dd214.pdf",
        labels={"11": GARBLED_LABEL_11},
        blocks={"11": WRAPPED_SPECIALTIES},
        label_on_value_line=("11",),
    )
    assert _occupations(resolve(read(pdf)[1])) == [
        ("25U60 2B SI GI NT SGT/ CHIEF", 134),
        ("25B4L NETWORK SYSTEMS OPERATOR", 281),
    ]


# The same label as the user's own form leaves it: its last line stands on its own, above
# the typed entries, and holds no value. Garbled this far it matches no text of the label,
# so only its size says it is label. "S/RS!" is drawn over both lines, as OCR left it.
TALL_WORD_11 = ("S/RS!", 20.0)
WRAPPED_LABEL_11 = GARBLED_LABEL_11.removesuffix(" " + TALL_WORD_11[0])


def test_block_11s_label_line_is_not_read_as_a_specialty(tmp_path):
    """The reported failure on the user's form. The last line of block 11's printed label
    came out as the start of the first specialty's title, because the line matches no text
    of the label any more. It is printed at the label's own size, and the entries under it
    are typed larger, which is what tells the two apart. The one word of another size on
    that line, which OCR left standing across both printed lines, goes with the line."""
    pdf = form.write_text_pdf(
        tmp_path / "dd214.pdf",
        labels={"11": WRAPPED_LABEL_11},
        blocks={"11": WRAPPED_SPECIALTIES},
        stray={"11": TALL_WORD_11},
    )
    assert _occupations(resolve(read(pdf)[1])) == [
        ("25U60 2B SI GI NT SGT/ CHIEF", 134),
        ("25B4L NETWORK SYSTEMS OPERATOR", 281),
    ]


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
    "variant",
    ["clean_pdf", "noisy_pdf", "overlap_pdf", pytest.param("ocr_pdf", marks=needs_tesseract)],
)
def test_personal_blocks_never_reach_facts_or_report(variant, request, capsys):
    assert _leaked(request.getfixturevalue(variant), capsys) == []


@pytest.mark.parametrize(
    ("omit", "refused"),
    [
        (("7a", "7b"), {"4a", "4b"}),  # 4a and 4b would grow down over the place of entry
        (("5",), {"4b"}),  # 4b would grow right over the date of birth
        (("3",), {"2"}),  # 2 would grow right over the SSN
        (("15a", "15b", "15c", "16", "17", "18"), {"13", "14"}),  # down over the remarks
    ],
)
def test_block_whose_bounding_label_is_lost_is_refused_not_grown(omit, refused, tmp_path, capsys):
    pdf = form.write_text_pdf(tmp_path / "dd214.pdf", omit=omit)
    assert _leaked(pdf, capsys) == []
    layout = read_form(*_loaded(pdf)).layout
    assert {r.block for r in layout.regions if r.status is Status.REFUSED} == refused
    notes = read(pdf)[0].notes
    assert all(any(n.startswith(f"Block {b} ") for n in notes) for b in refused)


def _loaded(pdf: Path):
    """What the reader is given for `pdf`: its words, their lines, and the scan behind them."""
    content = load_text(pdf)
    return content.words, content.lines, content.scan


def _leaked(pdf: Path, capsys) -> list[str]:
    """The fake personal values that reach the reader's text, the facts or the report."""
    doc, facts = read(pdf)
    outputs = [
        read_form(*_loaded(pdf)).text or "",
        json.dumps([asdict(doc), *map(asdict, facts), asdict(resolve(facts))], default=str),
    ]
    if DEFAULT_INDEX.exists():
        assert main(["translate", str(pdf), "-f", "json"]) == 0
        outputs.append(capsys.readouterr().out)
    return [v for v in form.SENSITIVE.values() for out in outputs if v.upper() in out.upper()]


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


def test_fillable_pdf_is_read_in_line_order_as_before(tmp_path):
    """Form field values have no word boxes, so reading by position would drop them."""
    pdf = form.write_text_pdf(tmp_path / "dd214.pdf", field="SEE ATTACHED")
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


@needs_tesseract
@needs_ocr_extra
def test_block_12_reads_whole_from_a_300_dpi_scan_with_no_text_layer(pdfs, clean_pdf):
    """The reported failure in the hosted deploy: most of block 12 came back as values
    that "could not be read", and one row as a row where no value was found.

    A page with no text layer is read by OCR alone, and a DD-214 is not one column of
    text: blocks 11 and 12 sit side by side and block 12 is a grid. In tesseract's
    one-column mode the words of two of its rows come back in one box, two rows tall, so a
    value is placed in the wrong row or in none, and the crop a cell is re-read from spans
    two rows and reads as nothing. In sparse-text mode each cell is boxed on its own.

    At 300 dpi, which is what an office scanner and a phone's scan app both produce. The
    test above draws its scan at 200 dpi, where one-column mode happened to survive.
    """
    png = form.rasterize(clean_pdf, pdfs / "scan-300.png", dpi=300)
    pdf = form.write_image_pdf(png, pdfs / "image-300.pdf", dpi=300)

    doc, facts = read(pdf, ocr=True)
    profile = resolve(facts)

    assert profile.service_time["net_active"] == NET_ACTIVE
    assert profile.service_time["foreign"] == FOREIGN
    assert profile.context.as_of == date(2020, 10, 3)  # block 12b
    assert [n for n in doc.notes if "block 12" in n] == []
    # Sparse-text mode reads one typed line of a wide block in pieces, each a line of its
    # own and not in the page's order, so block 14's entries come out of `_rejoin` or not
    # at all: "ADVANCED" and "LEADER COURSE, FOLLOWS" were two courses before it.
    assert _occupations(profile) == SPECIALTIES
    assert [
        (t.value.title, t.value.weeks, t.value.completed.year) for t in profile.training
    ] == COURSES
    assert [(a.value.name, a.value.count) for a in profile.awards] == AWARDS
    ocr = load_text(pdf, ocr=True)
    cells = read_form(ocr.words, ocr.lines, ocr.scan).layout.cells
    assert {c.status for c in cells} == {Status.READ}
