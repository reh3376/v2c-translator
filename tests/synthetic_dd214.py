"""A fictional DD-214 (AUG 2009 edition), drawn at test time. No PDF or image is committed.

The page copies the form's geometry: ruled boxes, small printed labels, typed values,
blocks 11/12 and 13/14 side by side, and block 12 as a 9 x 3 grid. Text is drawn in
row-major order across the whole page, so the content stream interleaves the columns the
way a scanned form's OCR text layer does. Every value is fake.
"""

from __future__ import annotations

import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

PAGE_W, PAGE_H = 612.0, 792.0
LABEL_FONT, LABEL_SIZE = "Helvetica", 6.5
VALUE_FONT, VALUE_SIZE = "Courier", 9.0

TITLE = "CERTIFICATE OF RELEASE OR DISCHARGE FROM ACTIVE DUTY"

# What the tests expect back.
BRANCH = "ARMY/RA"
RANK, PAY_GRADE = "SSG", "E06"
SPECIALTIES = (
    "35M20 HUMAN INTELLIGENCE COLLECTOR 8 YRS 3 MOS//"
    "35F10 INTELLIGENCE ANALYST 4 YRS 0 MOS//NOTHING FOLLOWS"
)
AWARDS = (
    "ARMY COMMENDATION MEDAL (2ND AWARD)//ARMY ACHIEVEMENT MEDAL (3RD AWARD)//"
    "ARMY GOOD CONDUCT MEDAL (4TH AWARD)//NATIONAL DEFENSE SERVICE MEDAL//"
    "GLOBAL WAR ON TERRORISM SERVICE MEDAL//ARMY SERVICE RIBBON//"
    "OVERSEAS SERVICE RIBBON (2)//NOTHING FOLLOWS"
)
COURSES = (
    "BASIC LEADER COURSE, 4 WEEKS, 2012//ADVANCED LEADER COURSE, 6 WEEKS, 2016//NOTHING FOLLOWS"
)
# Block 12 rows: (letter, label, YEAR(S), MONTH(S), DAY(S)).
RECORD = (
    ("a", "DATE ENTERED AD THIS PERIOD", "2008", "06", "19"),
    ("b", "SEPARATION DATE THIS PERIOD", "2020", "10", "03"),
    ("c", "NET ACTIVE SERVICE THIS PERIOD", "0012", "03", "15"),
    ("d", "TOTAL PRIOR ACTIVE SERVICE", "0000", "00", "00"),
    ("e", "TOTAL PRIOR INACTIVE SERVICE", "0000", "00", "00"),
    ("f", "FOREIGN SERVICE", "0001", "04", "11"),
    ("g", "SEA SERVICE", "0000", "00", "00"),
    ("h", "INITIAL ENTRY TRAINING", "0000", "04", "02"),
    ("i", "EFFECTIVE DATE OF PAY GRADE", "2016", "02", "01"),
)
# Fake values in the blocks the reader must never emit (1, 3, 5, 7, 8, 18, 19, 21-28).
SENSITIVE = {
    "name": "SAMPLE, ALEX TEST",
    "ssn": "000-00-0000",
    "dob": "19900101",
    "place_of_entry": "ANYTOWN, KY",
    "home_of_record": "456 MADEUP AVE ANYTOWN KY 00000",
    "station": "FORT EXAMPLE, KY",
    "remarks": "MEMBER SERVED IN EXAMPLELAND 20150301-20160301",
    "address": "123 FAKE ST ANYTOWN KY 00000",
    "relative": "SAMPLE, PAT",
    "character": "HONORABLE",
    "authority": "AR 635-200 CHAP 4",
    "separation_code": "KBK",
    "reentry_code": "RE-1",
    "narrative": "COMPLETION OF REQUIRED ACTIVE SERVICE",
}


@dataclass(frozen=True)
class Box:
    label: str
    x0: float
    top: float
    x1: float
    bottom: float
    value: str = ""


def _row(top: float, bottom: float, *cells: tuple[str, float, float, str]) -> list[Box]:
    return [Box(label, x0, top, x1, bottom, value) for label, x0, x1, value in cells]


S = SENSITIVE
BOXES: list[Box] = [
    *_row(
        60,
        84,
        ("1. NAME (Last, First, Middle)", 36, 300, S["name"]),
        ("2. DEPARTMENT, COMPONENT AND BRANCH", 300, 450, BRANCH),
        ("3. SOCIAL SECURITY NUMBER", 450, 576, S["ssn"]),
    ),
    *_row(
        84,
        108,
        ("4a. GRADE, RATE OR RANK", 36, 170, RANK),
        ("4b. PAY GRADE", 170, 230, PAY_GRADE),
        ("5. DATE OF BIRTH (YYYYMMDD)", 230, 380, S["dob"]),
        ("6. RESERVE OBLIGATION TERMINATION DATE (YYYYMMDD)", 380, 576, "20260101"),
    ),
    *_row(
        108,
        132,
        ("7a. PLACE OF ENTRY INTO ACTIVE DUTY", 36, 300, S["place_of_entry"]),
        (
            "7b. HOME OF RECORD AT TIME OF ENTRY (City and state, or complete address if known)",
            300,
            576,
            S["home_of_record"],
        ),
    ),
    *_row(
        132,
        156,
        ("8a. LAST DUTY ASSIGNMENT AND MAJOR COMMAND", 36, 300, "HHC 1ST BN EXAMPLE BDE"),
        ("8b. STATION WHERE SEPARATED", 300, 576, S["station"]),
    ),
    *_row(
        156,
        180,
        ("9. COMMAND TO WHICH TRANSFERRED", 36, 300, "USAR CON GP (ANNUAL TRAINING)"),
        ("10. SGLI COVERAGE", 300, 576, "$400,000"),
    ),
    *_row(
        180,
        330,
        (
            "11. PRIMARY SPECIALTY (List number, title and years and months in specialty. "
            "List additional specialty numbers and titles involving periods of one or more "
            "years.)",
            36,
            330,
            SPECIALTIES,
        ),
        ("12. RECORD OF SERVICE", 330, 576, ""),
    ),
    *_row(
        330,
        440,
        (
            "13. DECORATIONS, MEDALS, BADGES, CITATIONS AND CAMPAIGN RIBBONS AWARDED OR "
            "AUTHORIZED (All periods of service)",
            36,
            330,
            AWARDS,
        ),
        (
            "14. MILITARY EDUCATION (Course title, number of weeks, and month and year completed)",
            330,
            576,
            COURSES,
        ),
    ),
    *_row(
        440,
        470,
        ("15a. COMMISSIONED THROUGH SERVICE ACADEMY", 36, 200, "NO"),
        ("15b. COMMISSIONED THROUGH ROTC SCHOLARSHIP", 200, 380, "NO"),
        ("15c. ENLISTED UNDER LOAN REPAYMENT PROGRAM", 380, 576, "NO"),
    ),
    *_row(
        470,
        500,
        ("16. DAYS ACCRUED LEAVE PAID", 36, 200, "30.0 DAYS PAID"),
        (
            "17. MEMBER WAS PROVIDED COMPLETE DENTAL EXAMINATION AND ALL APPROPRIATE DENTAL "
            "SERVICES AND TREATMENT WITHIN 90 DAYS PRIOR TO SEPARATION",
            200,
            576,
            "YES",
        ),
    ),
    *_row(500, 560, ("18. REMARKS", 36, 576, S["remarks"] + "//NOTHING FOLLOWS")),
    *_row(
        560,
        590,
        ("19a. MAILING ADDRESS AFTER SEPARATION", 36, 330, S["address"]),
        ("19b. NEAREST RELATIVE", 330, 576, S["relative"]),
    ),
    *_row(
        590,
        614,
        ("20. MEMBER REQUESTS COPY 6 BE SENT TO DIR. OF VET AFFAIRS", 36, 576, "YES"),
    ),
    *_row(
        614,
        644,
        ("21. SIGNATURE OF MEMBER BEING SEPARATED", 36, 330, ""),
        ("22. OFFICIAL AUTHORIZED TO SIGN (Typed name, grade, title and signature)", 330, 576, ""),
    ),
    *_row(
        656,
        680,
        ("23. TYPE OF SEPARATION", 36, 330, "RELEASE FROM ACTIVE DUTY"),
        ("24. CHARACTER OF SERVICE (include upgrades)", 330, 576, S["character"]),
    ),
    *_row(
        680,
        704,
        ("25. SEPARATION AUTHORITY", 36, 330, S["authority"]),
        ("26. SEPARATION CODE", 330, 450, S["separation_code"]),
        ("27. REENTRY CODE", 450, 576, S["reentry_code"]),
    ),
    *_row(704, 728, ("28. NARRATIVE REASON FOR SEPARATION", 36, 576, S["narrative"])),
    *_row(
        728,
        758,
        ("29. DATES OF TIME LOST DURING THIS PERIOD (YYYYMMDD)", 36, 450, "NONE"),
        ("30. MEMBER REQUESTS COPY 4 (Initials)", 450, 576, "AT"),
    ),
]

# Block 12's grid, inside its box.
GRID_X0, GRID_X1 = 330, 576
COLUMNS = (("YEAR(S)", 456, 496), ("MONTH(S)", 496, 536), ("DAY(S)", 536, 576))
GRID_TOP, ROW_PITCH = 196.0, 14.0

# OCR-style confusions for the noisy variant: the drawn text, not the value it stands for.
NOISY_CELLS = {
    ("a", 2): "|9",  # bar for 1
    ("b", 1): "l0",  # l for 1
    ("c", 0): "OO12",  # O for 0
    ("c", 2): "1S",  # S for 5
    ("f", 0): "0'0o1",  # stray quote, o for 0
    ("f", 2): "I1",  # I for 1
    ("h", 1): "0?4",  # stray question mark
    ("i", 1): "O2",
    # Misreads no repair can undo: the reader must leave these rows out, not guess.
    ("d", 2): "8O",  # 80 days
    ("g", 1): "0B",
}
NOISY_LABELS = {
    "2. DEPARTMENT, COMPONENT AND BRANCH": "2, DEPART MENT, C0MPONENT AND BRANCH",
    "4b. PAY GRADE": "4b. PAY GRAOE",
    "12. RECORD OF SERVICE": "12. REC0RD 0F SERVICE",
    "14. MILITARY EDUCATION (Course title, number of weeks, and month and year completed)": (
        "14. MILI TARY EDUCATI0N (Course title, number of weeks, and month and year completed)"
    ),
}


@dataclass(frozen=True)
class _Text:
    top: float  # baseline, from the page's top edge
    x: float
    text: str
    font: str
    size: float
    then: tuple[float, str] | None = None  # more text at this x, in the same text run


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    from reportlab.lib.utils import simpleSplit

    return simpleSplit(text, font, size, width)


def _texts(*, noisy: bool, title: str) -> list[_Text]:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    out = [_Text(44, 160, title, "Helvetica-Bold", 10)]
    out.append(_Text(30, 36, "CAUTION: NOT TO BE USED FOR IDENTIFICATION PURPOSES", "Helvetica", 6))
    out.append(
        _Text(776, 36, "DD FORM 214, AUG 2009   PREVIOUS EDITION IS OBSOLETE.", "Helvetica", 6)
    )
    for box in BOXES:
        label = NOISY_LABELS.get(box.label, box.label) if noisy else box.label
        lines = _wrap(label, LABEL_FONT, LABEL_SIZE, box.x1 - box.x0 - 4)
        if box.label.startswith("12."):
            lines = _wrap(label, LABEL_FONT, LABEL_SIZE, COLUMNS[0][1] - box.x0 - 4)
        y = box.top + 7
        for line in lines:
            out.append(_Text(y, box.x0 + 2, line, LABEL_FONT, LABEL_SIZE))
            y += 7
        y += 4
        for line in _wrap(box.value, VALUE_FONT, VALUE_SIZE, box.x1 - box.x0 - 8):
            out.append(_Text(y + 3, box.x0 + 4, line, VALUE_FONT, VALUE_SIZE))
            y += 11
    for name, x0, x1 in COLUMNS:
        x = (x0 + x1 - stringWidth(name, LABEL_FONT, LABEL_SIZE)) / 2
        out.append(_Text(187, x, name, LABEL_FONT, LABEL_SIZE))
    for i, (letter, label, *cells) in enumerate(RECORD):
        top = GRID_TOP + i * ROW_PITCH
        out.append(_Text(top + 9, GRID_X0 + 4, f"{letter}. {label}", LABEL_FONT, LABEL_SIZE))
        for j, ((_, x0, x1), cell) in enumerate(zip(COLUMNS, cells, strict=True)):
            drawn = NOISY_CELLS.get((letter, j), cell) if noisy else cell
            x = (x0 + x1 - stringWidth(cell, VALUE_FONT, VALUE_SIZE)) / 2
            # Typed values sit a little above the printed label's baseline, as on a scan.
            out.append(_Text(top + 7.5, x, drawn, VALUE_FONT, VALUE_SIZE))
    if noisy:
        # A line-level OCR layer writes block 11's first line and row 12a's label as one run.
        first = next(t for t in out if t.text.startswith("35M20"))
        row_a = next(t for t in out if t.text.startswith("a. "))
        out = [t for t in out if t not in (first, row_a)]
        out.append(_Text(row_a.top, first.x, first.text, "Courier", 6.5, (row_a.x, row_a.text)))
    return out


def write_text_pdf(
    path: Path, *, noisy: bool = False, title: str = TITLE, field: str | None = None
) -> Path:
    """The form as a PDF with a text layer, drawn in row-major order across the page.

    `noisy` draws what a scan's OCR layer holds: confusions (O for 0, l for 1, stray
    punctuation, split and misread label words), two cells no repair can undo, and one text
    run that crosses from block 11 into block 12. `field` adds a fillable form field that
    holds that value.
    """
    from reportlab.pdfgen.canvas import Canvas

    c = Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
    c.setLineWidth(0.6)
    for box in BOXES:
        c.rect(box.x0, PAGE_H - box.bottom, box.x1 - box.x0, box.bottom - box.top)
    for i in range(len(RECORD) + 1):
        y = PAGE_H - (GRID_TOP + i * ROW_PITCH)
        c.line(GRID_X0, y, GRID_X1, y)
    for _, x0, _ in COLUMNS:
        c.line(x0, PAGE_H - 182, x0, PAGE_H - (GRID_TOP + len(RECORD) * ROW_PITCH))
    if field:
        c.acroForm.textfield(name="remarks", value=field, x=40, y=PAGE_H - 550, borderWidth=0)
    for t in sorted(_texts(noisy=noisy, title=title), key=lambda t: (t.top, t.x)):
        c.setFont(t.font, t.size)
        if t.then:
            _draw_run(c, t)
            continue
        c.drawString(t.x, PAGE_H - t.top, t.text)
    c.save()
    return path


def tools_available() -> bool:
    return bool(shutil.which("tesseract") and shutil.which("pdftoppm"))


def rasterize(
    pdf: Path,
    out_png: Path,
    *,
    dpi: int = 200,
    blur: float = 0.6,
    noise: int = 12,
    rotate: float = 0.0,
    seed: int = 214,
) -> Path:
    """Render `pdf` page 1 to a grayscale PNG the way a scanner would: blur and speckle."""
    from PIL import Image, ImageFilter

    stem = out_png.with_suffix("")
    subprocess.run(
        ["pdftoppm", "-r", str(dpi), "-gray", "-png", "-singlefile", str(pdf), str(stem)],
        check=True,
    )
    img = Image.open(stem.with_suffix(".png")).convert("L")
    if rotate:
        img = img.rotate(rotate, resample=Image.Resampling.BICUBIC, fillcolor=255, expand=False)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if noise:
        rng = random.Random(seed)
        speckle = Image.frombytes("L", img.size, rng.randbytes(img.width * img.height))
        img = Image.blend(img, speckle, noise / 255)
    img.save(out_png, dpi=(dpi, dpi))
    return out_png


def write_ocr_pdf(png: Path, out_pdf: Path, *, psm: int = 11) -> Path:
    """OCR `png` with tesseract into a PDF that carries the image and a text layer.

    psm 11 (sparse text) suits a form of small boxed fields; tesseract's default, psm 3,
    misreads more of block 12's digits on these scans.
    """
    subprocess.run(
        ["tesseract", str(png), str(out_pdf.with_suffix("")), "--psm", str(psm), "pdf"],
        check=True,
        capture_output=True,
    )
    return out_pdf


def write_image_pdf(png: Path, out_pdf: Path, *, dpi: int = 200) -> Path:
    """`png` as an image-only PDF: a scan with no text layer."""
    from PIL import Image

    Image.open(png).convert("L").save(out_pdf, "PDF", resolution=float(dpi))
    return out_pdf


def _draw_run(c, t: _Text) -> None:
    """`t.text`, then `t.then` at its own x, as one TJ: one run the way an OCR layer writes a
    line, with a kerning gap in place of the space between two blocks."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    x, rest = t.then
    gap = x - t.x - stringWidth(t.text, t.font, t.size)
    font = c._doc.getInternalFontName(t.font)
    c._code.append(
        f"BT {font} {t.size} Tf 1 0 0 1 {t.x} {PAGE_H - t.top} Tm "
        f"[({t.text}) {-gap / t.size * 1000:.0f} ({rest})] TJ ET"
    )
