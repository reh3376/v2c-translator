"""Read a DD-214 page by where its blocks sit, not by the order of its lines.

On the form, block 11 sits beside block 12 and block 13 beside block 14, and block 12 is
a grid of rows against YEAR(S)/MONTH(S)/DAY(S) columns. A text layer or OCR reads such a
page line by line across both columns, which mixes the blocks. This module finds each
block's printed label, boxes the block from its neighbours' labels, takes the words inside
the box, and writes the blocks the extractor needs back out as plain text, one after
another, in the shape `parse.segment()` already reads. No other block is written, so the
blocks that hold personal data (name, SSN, birth date, addresses, remarks, signatures,
separation codes) never leave this module. No word inside such a block's box is written
either, and a written block whose box cannot be bounded away from one is not read.
"""

from __future__ import annotations

import math
import re
import statistics
from calendar import monthrange
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from functools import partial
from itertools import accumulate, combinations, pairwise

from rapidfuzz import fuzz
from rapidfuzz.distance import Indel

from ..extract import ExtractionError, Scan, ScanPages, Word
from ..parse import MAX_SERVICE_YEARS, detect_version

# Fuzzy-match floor (0-100) for a printed label against a line of OCR'd text.
LABEL_MATCH = 85
# How many of a printed label's characters are matched against a line. A label that wraps
# onto a second line, or whose line runs into the label beside it, is still recognised by
# the characters it starts with.
LABEL_PREFIX = 24
# Fuzzy-match floor for one line of a printed label that wraps. A short piece of a label
# loses more of its score to the same OCR noise than the whole label does, so this sits
# below LABEL_MATCH: the piece only has to be text the label holds.
LABEL_LINE_MATCH = 80
# Fuzzy-match floor for the label's tail at the start of a line that goes on to a value,
# how many characters of label that tail must hold, and how far its length may stand from
# the label's own. See _label_tail().
LABEL_TAIL_MATCH = 75
MIN_LABEL_TAIL = 5
TAIL_SLACK = 4
# What a line must hold after the label's tail for the rest of it to be a value.
MIN_VALUE = 4
# Fuzzy-match floor for one of block 12's column headings, which are single words.
HEADING_MATCH = 75
# A page with fewer labels found than this is not read by position.
MIN_LABELS = 5
NOT_READ = (
    "Too few DD-214 block labels were found to read the page by block position, so it was "
    "read line by line. Blocks that sit side by side may be mixed."
)


@dataclass(frozen=True, slots=True)
class Row:
    letter: str
    label: str
    is_date: bool  # a date (YYYY MM DD) rather than a length of service


@dataclass(frozen=True, slots=True)
class Bounds:
    """The labels that stop a written block's box before the nearest block that holds
    personal data: one label from `beside` must sit to its right and one from `below` under
    it. A side with no such block lies open."""

    beside: tuple[str, ...] = ()
    below: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Edition:
    name: str  # parse.detect_version()'s name for the layout
    title: str  # written first, so detect_version() knows the layout
    labels: tuple[tuple[str, str], ...]  # (block, printed label) for every block on the form
    written: tuple[str, ...]  # the blocks to write, in form order
    record: str  # the record of service, read as a grid
    rows: tuple[Row, ...]
    withheld: tuple[str, ...]  # blocks that hold personal data: no word in their box is written
    bounds: tuple[tuple[str, Bounds], ...]  # (written block, the labels that must bound it)


DURATION, DATE = False, True
ABOVE_REMARKS = ("15a", "15b", "15c", "16", "17", "18")
EDITION_2000 = Edition(
    name="2000",
    title="CERTIFICATE OF RELEASE OR DISCHARGE FROM ACTIVE DUTY",
    labels=(
        ("1", "NAME (Last, First, Middle)"),
        ("2", "DEPARTMENT, COMPONENT AND BRANCH"),
        ("3", "SOCIAL SECURITY NUMBER"),
        ("4a", "GRADE, RATE OR RANK"),
        ("4b", "PAY GRADE"),
        ("5", "DATE OF BIRTH (YYYYMMDD)"),
        ("6", "RESERVE OBLIGATION TERMINATION DATE (YYYYMMDD)"),
        ("7a", "PLACE OF ENTRY INTO ACTIVE DUTY"),
        ("7b", "HOME OF RECORD AT TIME OF ENTRY (City and state, or complete address if known)"),
        ("8a", "LAST DUTY ASSIGNMENT AND MAJOR COMMAND"),
        ("8b", "STATION WHERE SEPARATED"),
        ("9", "COMMAND TO WHICH TRANSFERRED"),
        ("10", "SGLI COVERAGE"),
        (
            "11",
            "PRIMARY SPECIALTY (List number, title and years and months in specialty. List "
            "additional specialty numbers and titles involving periods of one or more years.)",
        ),
        ("12", "RECORD OF SERVICE"),
        (
            "13",
            "DECORATIONS, MEDALS, BADGES, CITATIONS AND CAMPAIGN RIBBONS AWARDED OR AUTHORIZED "
            "(All periods of service)",
        ),
        ("14", "MILITARY EDUCATION (Course title, number of weeks, and month and year completed)"),
        ("15a", "COMMISSIONED THROUGH SERVICE ACADEMY"),
        ("15a", "MEMBER CONTRIBUTED TO POST-VIETNAM ERA VETERANS' EDUCATIONAL ASSISTANCE PROGRAM"),
        ("15b", "COMMISSIONED THROUGH ROTC SCHOLARSHIP"),
        ("15b", "HIGH SCHOOL GRADUATE OR EQUIVALENT"),
        ("15c", "ENLISTED UNDER LOAN REPAYMENT PROGRAM"),
        ("16", "DAYS ACCRUED LEAVE PAID"),
        ("17", "MEMBER WAS PROVIDED COMPLETE DENTAL EXAMINATION"),
        ("18", "REMARKS"),
        ("19a", "MAILING ADDRESS AFTER SEPARATION"),
        ("19b", "NEAREST RELATIVE"),
        ("20", "MEMBER REQUESTS COPY 6 BE SENT TO"),
        ("21", "SIGNATURE OF MEMBER BEING SEPARATED"),
        ("22", "OFFICIAL AUTHORIZED TO SIGN"),
        ("23", "TYPE OF SEPARATION"),
        ("24", "CHARACTER OF SERVICE (include upgrades)"),
        ("25", "SEPARATION AUTHORITY"),
        ("26", "SEPARATION CODE"),
        ("27", "REENTRY CODE"),
        ("28", "NARRATIVE REASON FOR SEPARATION"),
        ("29", "DATES OF TIME LOST DURING THIS PERIOD (YYYYMMDD)"),
        ("30", "MEMBER REQUESTS COPY 4 (Initials)"),
    ),
    written=("2", "4a", "4b", "11", "12", "13", "14"),
    record="12",
    rows=(
        Row("a", "DATE ENTERED AD THIS PERIOD", DATE),
        Row("b", "SEPARATION DATE THIS PERIOD", DATE),
        Row("c", "NET ACTIVE SERVICE THIS PERIOD", DURATION),
        Row("d", "TOTAL PRIOR ACTIVE SERVICE", DURATION),
        Row("e", "TOTAL PRIOR INACTIVE SERVICE", DURATION),
        Row("f", "FOREIGN SERVICE", DURATION),
        Row("g", "SEA SERVICE", DURATION),
        Row("h", "INITIAL ENTRY TRAINING", DURATION),
        Row("i", "EFFECTIVE DATE OF PAY GRADE", DATE),
    ),
    withheld=(
        *("1", "3", "5", "6", "7a", "7b", "8a", "8b", "9", "18", "19a", "19b", "21", "22"),
        *(str(block) for block in range(23, 31)),
    ),
    bounds=(
        ("2", Bounds(beside=("3",), below=("4a", "4b", "5", "6"))),
        ("4a", Bounds(beside=("4b", "5"), below=("7a", "7b"))),
        ("4b", Bounds(beside=("5",), below=("7a", "7b"))),
        ("11", Bounds(below=("13", "14", *ABOVE_REMARKS))),
        ("13", Bounds(below=ABOVE_REMARKS)),
        ("14", Bounds(below=ABOVE_REMARKS)),
    ),
)
EDITIONS = (EDITION_2000,)
COLUMNS = ("YEARS", "MONTHS", "DAYS")  # block 12's headings, squashed
CELL_DIGITS = (4, 2, 2)  # the form prints YEAR(S) as 4 digits, MONTH(S) and DAY(S) as 2
# Block 12's rows a and b are the dates this period of service ran between, and row c is
# its length, counted inclusively. Time lost (block 29) is not read here, so a length that
# does not follow from the dates is reported as a note, not corrected.
ENTERED, SEPARATED, NET_ACTIVE = "a", "b", "c"
# How far the step between block 12's rows may stand from one row's share of the block's
# height before what is being measured is taken to be something other than its rows.
PITCH_OF_BAND = (0.6, 1.6)
RECORD_DAYS_SLACK = 3
# What OCR writes for a digit in a cell that holds nothing else: a zero read as a letter or
# a bracket, a one read as a stroke. "N" stands for a zero only in a two-digit cell, where
# the form prints "00" and OCR runs the pair together as "NO".
OCR_DIGITS = str.maketrans("OoQDIl|", "0000111")
ZERO_BRACKETS_RE = re.compile(r"\(\s*\)")
CELL_DIGIT_WHITELIST = "-c tessedit_char_whitelist=" + "".join(map(str, range(10)))
CELL_PAD = 1.0  # margin around a cell's box when it is cut out of the page image
DARK = 140  # grey below this is ink, when a crop is read in black and white


@dataclass(frozen=True, slots=True)
class Try:
    """How a cell is cut out of the page image and read: the margin around its box, how far
    the crop is magnified, the page-segmentation mode tesseract reads it in, and whether the
    crop is made black and white first."""

    pad: float
    zoom: float
    psm: int
    black_and_white: bool


# What a cell is read at, in order, until a reading is the digits the cell holds. Measured
# on the 27 cells of a scanned fictional form: sparse-text mode (11) read every one of
# them, single-line mode (7) 14, and magnifying the crop first helped only where it was
# made black and white too. The second and third try give a cell the first one misses a
# wider margin, in case its box sits a little off the page's own, and a second reader.
REREAD_TRIES = (
    Try(CELL_PAD, 1.0, 11, False),
    Try(3 * CELL_PAD, 1.0, 11, True),
    Try(3 * CELL_PAD, 2.0, 7, True),
)
OCR_TOOLS_MISSING = (
    "Some block 12 values were unreadable in the PDF's text layer; installing the OCR tools "
    "(see README) lets them be re-read from the scan."
)
RULE_RE = re.compile(r"[|\[\]_!\u2013\u2014]+")  # a ruled line read as text
SPLIT_SEPARATOR_RE = re.compile(r"/\s+/")  # OCR's "/ /" for the "//" between entries


Box = tuple[float, float, float, float]  # x0, top, x1, bottom


class Status(StrEnum):
    """What the reader did with a block, or with a cell of block 12."""

    READ = "read"
    REFUSED = "refused"  # boxed, but its box is not bounded or its value could not be read
    NOT_FOUND = "not-found"  # its label was not found, so it has no box
    WITHHELD = "withheld"  # it holds personal data: no word in its box is written


@dataclass(frozen=True, slots=True)
class Region:
    """A block's box, and the words inside it that the reader writes."""

    block: str
    status: Status
    box: Box | None = None
    words: tuple[Word, ...] = ()


@dataclass(frozen=True, slots=True)
class Reread:
    """What came back when a cell was cut out of the page image and read again. The reading
    itself is not kept, only its shape, so a layout report can show why a cell failed
    without showing a character of what it holds."""

    crop: Box  # the box cut out, in the image's own pixels
    zoom: float  # how much it was magnified before being read
    shape: str  # the kind and length of what came back ("D2"), or "none"
    accepted: bool  # whether it read as the digits the cell holds


@dataclass(frozen=True, slots=True)
class Cell:
    """One cell of block 12's grid: a row's YEAR(S), MONTH(S) or DAY(S)."""

    row: str  # the row's letter
    column: str  # one of COLUMNS
    status: Status
    box: Box | None = None
    words: tuple[Word, ...] = ()
    value: str = ""  # its digits, once the whole row reads as a date or a length of service
    reread: Reread | None = None  # set when the cell was read again from the page image


@dataclass(frozen=True, slots=True)
class Layout:
    """Where the reader boxed each block it writes on one page, and what it did with each."""

    page: int
    regions: tuple[Region, ...]
    cells: tuple[Cell, ...]


@dataclass(frozen=True, slots=True)
class Form:
    """What the layout reader made of a page: the text to parse, or None to parse the page
    in line order, notes on what it could not read, and the boxes it read."""

    text: str | None
    notes: tuple[str, ...] = ()
    layout: Layout | None = None


@dataclass(frozen=True, slots=True)
class _Page:
    """The page image a cell can be read again from, when there is one. `missing_tools`
    says the page is a scan but the OCR tools that would read it are not installed."""

    scan: Scan | None = None
    missing_tools: bool = False


@dataclass(frozen=True, slots=True)
class _Read:
    """One cell as it was read: its digits, or None when no reading of it was digits."""

    digits: str | None
    reread: Reread | None = None
    missing_tools: bool = False


@dataclass(frozen=True, slots=True)
class _Label:
    key: str  # a block ("11") or a block 12 row ("12c")
    words: tuple[Word, ...]
    score: float

    @property
    def x0(self) -> float:
        return min(w.x0 for w in self.words)

    @property
    def top(self) -> float:
        return min(w.top for w in self.words)


def read_form(
    words: Sequence[Word],
    lines: Sequence[tuple[Word, ...]] = (),
    scan: ScanPages | None = None,
) -> Form:
    """Read the DD-214 page among `words` by position: the page with the most labels found.

    `lines` are the lines the words' source read them in (OCR's own lines); without them the
    source's order is cut into lines here. A printed label is matched against those lines
    and never against a regrouping of the words, because on a scan a small label row and the
    typed row under it overlap: regrouped, their words interleave and no label reads whole.

    `scan` gives the pages as images, so a block 12 cell the text layer garbled can be read
    again from the image.
    """
    if not words:
        return Form(None)  # Plain text: no positions to read by.
    if detect_version(_text(words)) not in ("unknown", *(ed.name for ed in EDITIONS)):
        return Form(None)  # Another edition (2022): its geometry is not known here.
    pages: dict[int, list[Word]] = {}
    for w in words:
        pages.setdefault(w.page, []).append(w)
    source = {n: [ln for ln in lines if ln and ln[0].page == n] for n in pages}
    found = max(
        (
            (ed, page, *_find_labels(source[n] or _reading_lines(page), ed))
            for n, page in pages.items()
            for ed in EDITIONS
        ),
        key=lambda f: (len(f[2]) + len(f[3]), sum(lb.score for lb in f[2].values())),
        default=None,
    )
    if found is None or len(found[2]) < MIN_LABELS:
        return Form(None, (NOT_READ,))
    edition, page, blocks, rows = found
    tol = 0.5 * _text_height(page)
    if not any(
        abs(a.top - b.top) <= tol and abs(a.x0 - b.x0) > 10 * tol
        for a, b in combinations(blocks.values(), 2)
    ):
        return Form(None)  # One block per line: line order is already block order.
    source_lines = source[page[0].page] or _reading_lines(page)
    layout, notes = _locate(edition, page, blocks, rows, tol, scan)
    return Form(_write(edition, layout, source_lines), tuple(notes), layout)


def _locate(
    edition: Edition,
    page: list[Word],
    blocks: dict[str, _Label],
    rows: dict[str, _Label],
    tol: float,
    scan: ScanPages | None = None,
) -> tuple[Layout, list[str]]:
    """Box each block the reader writes, and block 12's cells, from the labels found.

    The boxes of the blocks that hold personal data are boxed first, and no word inside one
    is written. A written block is refused when a label that keeps its box off such a block
    was not found: without it the box would grow over that block, whose own label may also
    be lost."""
    page_no = page[0].page
    page = [w for w in page if not RULE_RE.fullmatch(w.text)]
    rows = _aligned(rows, tol)
    right = max(w.x1 for w in page) + tol
    bottom = max(w.bottom for w in page) + tol

    def box(label: _Label) -> tuple[Box, set[str], set[str]]:
        return _box(label, blocks.values(), rows.values(), right, bottom, tol)

    withheld = [
        Region(b, Status.WITHHELD, box(blocks[b])[0]) for b in edition.withheld if b in blocks
    ]
    page = [w for w in page if not any(_inside(w, r.box) for r in withheld)]
    bounds = dict(edition.bounds)
    regions: list[Region] = []
    cells: list[Cell] = []
    notes: list[str] = []
    for block in edition.written:
        if block == edition.record:
            # Block 12's own label, or else its first row label, anchors its grid.
            anchor = blocks.get(block) or min(rows.values(), key=lambda lb: lb.top, default=None)
            grid = box(anchor)[0] if anchor else None
            cells, row_notes = _record(
                edition, page, anchor, grid, tol, partial(_scan_page, scan, page_no)
            )
            notes += row_notes
            continue
        name = _name(edition, block).lower()
        if block not in blocks:
            regions.append(Region(block, Status.NOT_FOUND))
            notes.append(f"Block {block} ({name}) was not found on the page; not read.")
            continue
        b, beside, below = box(blocks[block])
        need = bounds.get(block, Bounds())
        sides = {"to the right of": (need.beside, beside), "below": (need.below, below)}
        unbounded = [side for side, (want, got) in sides.items() if want and not got & set(want)]
        if unbounded:
            regions.append(Region(block, Status.REFUSED, b))
            notes.append(
                f"Block {block} ({name}) was not read: no block label was found "
                f"{' or '.join(unbounded)} it, so its box could reach a block with personal data."
            )
            continue
        # The label is printed at the top of its block, so a word above it is the block
        # above's: on a blurry scan one such word reaches into this box's top margin.
        inside = tuple(w for w in page if _inside(w, b) and _cy(w) >= blocks[block].top)
        regions.append(Region(block, Status.READ, b, inside))
    return Layout(page_no, (*regions, *withheld), tuple(cells)), notes


def _write(edition: Edition, layout: Layout, lines: Sequence[tuple[Word, ...]]) -> str:
    """The blocks read, as plain text in the shape `parse.segment()` reads. A block's words
    keep the lines their source read them in, so a printed label and the value typed under
    it stay apart even where their boxes overlap."""
    out = [edition.title]
    regions = {r.block: r for r in layout.regions}
    for block in edition.written:
        name = _name(edition, block)
        if block == edition.record:
            out += [f"{block}. {name}", *_record_lines(edition, layout.cells)]
            continue
        if regions[block].status is not Status.READ:
            continue
        in_box = _drop_label(
            _grouped(lines, regions[block].words), block + _printed(edition, block)
        )
        text = [_text(line) for line in in_box]
        # With "//" between entries, a line break in the box is only a wrap. The "//" may
        # itself be split, by OCR into "/ /" or by the wrap, so look for it in the joined box.
        joined = SPLIT_SEPARATOR_RE.sub("//", " ".join(text))
        out += [f"{block}. {name}", *([joined] if "//" in joined else text)]
    return "\n".join(out)


def _printed(edition: Edition, block: str) -> str:
    """The first label listed for `block`."""
    return next(text for b, text in edition.labels if b == block)


def _name(edition: Edition, block: str) -> str:
    return _head(_printed(edition, block))


# --------------------------------------------------------------------------- labels


def _find_labels(
    lines: list[tuple[Word, ...]], edition: Edition
) -> tuple[dict[str, _Label], dict[str, _Label]]:
    """The block labels and the record of service's row labels found on the page, keyed by
    block and by row letter. No word belongs to two labels, so "i. EFFECTIVE DATE OF PAY
    GRADE" cannot pass for "4b. PAY GRADE"."""
    blocks = [(block, block + _head(text)) for block, text in edition.labels]
    rows = [(edition.record + row.letter, row.letter + row.label) for row in edition.rows]
    found = _assign(lines, blocks + rows)
    return (
        {key: found[key] for key, _ in blocks if key in found},
        {key[len(edition.record) :]: found[key] for key, _ in rows if key in found},
    )


def _assign(lines: Iterable[tuple[Word, ...]], wanted: list[tuple[str, str]]) -> dict[str, _Label]:
    """Best match for each (key, text) in `lines`, greedily by score, no word used twice.

    Only a label's first LABEL_PREFIX characters are matched, so a label that wraps onto a
    second line, or a line that holds the label beside it too, still scores as itself."""
    candidates = []
    for line in lines:
        squashed, owner = _squash(line)
        size = Counter(owner)
        for key, text in wanted:
            score, span = _match(_squash_text(text)[:LABEL_PREFIX], squashed)
            # A word is the label's when most of its characters matched.
            hits = Counter(owner[i] for i in span)
            words = tuple(w for i, w in enumerate(line) if 2 * hits[i] > size[i])
            if score >= LABEL_MATCH and words:
                candidates.append(_Label(key, words, score))
    found: dict[str, _Label] = {}
    used: set[int] = set()
    for c in sorted(candidates, key=lambda c: (-c.score, c.top)):
        if c.key not in found and not used & {id(w) for w in c.words}:
            found[c.key] = c
            used |= {id(w) for w in c.words}
    return found


def _match(needle: str, line: str) -> tuple[float, range]:
    """How well `needle` appears in `line` (0-100), and the characters of `line` it matched."""
    if not needle or not line:
        return 0.0, range(0)
    if len(line) <= len(needle):
        score, start, end = fuzz.ratio(needle, line), 0, len(line)
    else:
        m = fuzz.partial_ratio_alignment(needle, line)
        score, start, end = m.score, m.dest_start, m.dest_end
    # The alignment window has the needle's length; trim what it holds but did not match.
    same = [op for op in Indel.opcodes(needle, line[start:end]) if op.tag == "equal"]
    if not same:
        return 0.0, range(0)
    return score, range(start + same[0].dest_start, start + same[-1].dest_end)


def _head(label: str) -> str:
    """A printed label without its parenthetical instructions."""
    return label.split("(")[0].strip()


def _grouped(lines: Sequence[tuple[Word, ...]], words: Iterable[Word]) -> list[tuple[Word, ...]]:
    """`words` cut into the lines their source read them in, top to bottom."""
    keep = {id(w) for w in words}
    out = [line for line in (tuple(w for w in ln if id(w) in keep) for ln in lines) if line]
    return sorted(out, key=lambda line: min(_cy(w) for w in line))


def _drop_label(lines: list[tuple[Word, ...]], label: str) -> list[tuple[Word, ...]]:
    """The box's lines after its printed label, which may wrap onto several lines and in any
    order: a parenthetical the form prints last can sit on the line above the one before it.
    So each line the label holds is dropped until one it does not hold, which is a value.

    On a scan the label's last line and the first typed line are read as one line. That
    line's own start is then the label's tail ("...periods of one or more years.)"), and is
    taken off it; left on, the tail reads as part of the first value on the form.
    """
    target = _squash_text(label)
    for i, line in enumerate(lines):
        squashed, owner = _squash(line)
        tail = _label_tail(squashed, target)
        if tail and len(squashed) - tail >= MIN_VALUE:
            value = {owner[j] for j in range(tail, len(owner))}
            return [tuple(w for n, w in enumerate(line) if n in value), *lines[i + 1 :]]
        if fuzz.partial_ratio(squashed, target) < LABEL_LINE_MATCH:
            return lines[i:]
    return []


def _label_tail(squashed: str, target: str) -> int:
    """How many characters at the start of a line the printed label's own tail covers; 0
    when the line starts with a value.

    The tail runs to the label's end, because the value follows it, so each candidate
    length is scored against the label's last characters, give or take TAIL_SLACK for what
    OCR dropped or added. The best score wins rather than the longest match: a longer piece
    of the line goes on scoring against a sliding window of so long a label, and would eat
    the value. On the reported form a garbled tail scores 80 and a line that starts with a
    value scores at most 54.
    """
    best = (0.0, 0)
    for n in range(MIN_LABEL_TAIL, min(len(squashed), len(target)) + 1):
        widths = range(max(1, n - TAIL_SLACK), min(len(target), n + TAIL_SLACK) + 1)
        score = max(fuzz.ratio(squashed[:n], target[len(target) - k :]) for k in widths)
        if score > best[0]:
            best = (score, n)
    return best[1] if best[0] >= LABEL_TAIL_MATCH else 0


def _squash(words: Iterable[Word]) -> tuple[str, list[int]]:
    """Upper-case letters and digits only, so spacing and punctuation noise don't count,
    with the index of the word each character came from."""
    chars, owner = [], []
    for i, w in enumerate(words):
        for c in w.text.upper():
            if c.isalnum():
                chars.append(c)
                owner.append(i)
    return "".join(chars), owner


def _squash_text(text: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", text.upper())


def shape(text: str) -> str:
    """A text's shape code: its kind of characters and its length, never a character. What
    a layout report may show of a word or of a reading, and all it may show."""
    if all(c.isdigit() for c in text):
        kind = "D"
    elif all(c.isalpha() for c in text):
        kind = "A"
    elif not any(c.isalnum() for c in text):
        kind = "P"
    else:
        kind = "M"
    return f"{kind}{len(text)}"


# --------------------------------------------------------------------------- geometry


def _cx(w: Word) -> float:
    return (w.x0 + w.x1) / 2


def _cy(w: Word) -> float:
    return (w.top + w.bottom) / 2


def _text_height(words: Sequence[Word]) -> float:
    return statistics.median(w.bottom - w.top for w in words)


def _reading_lines(words: Sequence[Word]) -> list[tuple[Word, ...]]:
    """Words in the order their source gives them, cut where the next word leaves the line:
    it rises or drops off it, or starts left of the word before.

    This keeps the source's own lines, which hold a printed label apart from the typed value
    under it even where their boxes overlap. Regrouping the page's words by height instead,
    as this module used to, interleaves such a pair and neither reads whole."""
    lines: list[list[Word]] = []
    for w in words:
        prev = lines[-1][-1] if lines else None
        tol = 0.5 * max(w.bottom - w.top, prev.bottom - prev.top) if prev else 0
        if prev and abs(_cy(w) - _cy(prev)) <= tol and w.x0 >= prev.x0:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [tuple(line) for line in lines]


def _text(line: Iterable[Word]) -> str:
    return " ".join(w.text for w in line)


def _aligned(rows: dict[str, _Label], tol: float) -> dict[str, _Label]:
    """The row labels that sit in one column; a match elsewhere on the page is a stray."""
    if not rows:
        return rows
    mid = statistics.median(lb.x0 for lb in rows.values())
    return {k: lb for k, lb in rows.items() if abs(lb.x0 - mid) <= 5 * tol}


def _box(
    label: _Label,
    blocks: Iterable[_Label],
    rows: Iterable[_Label],
    right: float,
    bottom: float,
    tol: float,
) -> tuple[Box, set[str], set[str]]:
    """The block under `label`: down to the next row of block labels, and right to the
    first label beside it. Block 12's row labels count as beside block 11, so block 11
    stays bounded when OCR loses block 12's own label. Also the keys of the labels beside
    it and below it, any of which bounds the box on that side."""
    blocks = list(blocks)
    below = [b for b in blocks if b.top > label.top + tol]
    y1 = min((b.top for b in below), default=bottom)
    beside = [
        b for b in [*blocks, *rows] if b.x0 > label.x0 + 5 * tol and label.top - tol <= b.top < y1
    ]
    x1 = min((b.x0 for b in beside), default=right)
    box = (label.x0 - tol, label.top - tol, x1 - tol, y1 - tol)
    return box, {b.key for b in beside}, {b.key for b in below}


def _inside(w: Word, box: Box) -> bool:
    x0, top, x1, bottom = box
    return x0 <= _cx(w) < x1 and top <= _cy(w) < bottom


# --------------------------------------------------------------------------- block 12


def _record(
    edition: Edition,
    page: list[Word],
    anchor: _Label | None,
    box: Box | None,
    tol: float,
    page_scan: Callable[[], Scan | None],
) -> tuple[list[Cell], list[str]]:
    """Block 12 read as a grid: its columns from the YEAR(S)/MONTH(S)/DAY(S) headings, and
    its rows by where each value sits down the column.

    The row labels do not place the rows. On a scan they sit a few points off the values
    they name, by more than the rows are apart, and some are lost altogether, so a box drawn
    around a label takes the row above or below it. The values themselves are a clean grid:
    one to a row, in row order, down each column.
    """
    block = edition.record
    rows = edition.rows
    unboxed = [Cell(row.letter, col, Status.NOT_FOUND) for row in rows for col in COLUMNS]
    if anchor is None:
        return unboxed, [f"Block {block} was not found on the page; not read."]
    headings = _headings(page, anchor)
    if headings is None:
        return unboxed, [
            f"Block {block}'s YEAR(S)/MONTH(S)/DAY(S) headings were not found; not read."
        ]
    columns = _columns(headings)
    floor = box[3] if box else max(w.bottom for w in page)
    stacks = {
        name: _stack(
            [w for w in page if x0 <= _cx(w) < x1 and headings[name].bottom < _cy(w) < floor],
            tol,
        )
        for name, (x0, x1) in columns.items()
    }
    placed = _place(stacks, max(h.bottom for h in headings.values()), floor, len(rows))
    if placed is None:
        return unboxed, [f"Block {block}'s rows could not be told apart; not read."]

    cells: list[Cell] = []
    notes: list[str] = []
    missing_tools = False
    for i, row in enumerate(rows):
        name = f"block {block}{row.letter} ({row.label.lower()})"
        words = {column: placed[column].get(i, ()) for column in columns}
        band = _band(words.values())
        if band is None:
            notes.append(f"No value was found in {name}; not read.")
            cells += [Cell(row.letter, column, Status.NOT_FOUND) for column in COLUMNS]
            continue
        # Every cell of a row is boxed from the row's own band, not from its own words, so
        # a cell the text layer left empty still has the box the page image is cut at.
        top, bottom = band
        boxes = {name: (x0, top, x1, bottom) for name, (x0, x1) in columns.items()}
        reads = [
            _cell_digits(_cell(words[column]), width, boxes[column], page_scan)
            for column, width in zip(COLUMNS, CELL_DIGITS, strict=True)
        ]
        missing_tools = missing_tools or any(read.missing_tools for read in reads)
        attempts = {c: read.reread for c, read in zip(COLUMNS, reads, strict=True)}
        if _row_value([read.digits for read in reads], row.is_date) is None:
            notes.append(f"The value of {name} could not be read; not used.")
            cells += [
                Cell(row.letter, c, Status.REFUSED, boxes[c], words[c], reread=attempts[c])
                for c in COLUMNS
            ]
            continue
        cells += [
            Cell(row.letter, c, Status.READ, boxes[c], words[c], read.digits or "", attempts[c])
            for c, read in zip(COLUMNS, reads, strict=True)
        ]
    if missing_tools:
        notes.append(OCR_TOOLS_MISSING)
    return cells, notes + _record_check(edition, cells)


def _band(cells: Iterable[tuple[Word, ...]]) -> tuple[float, float] | None:
    """How far down the page one row of block 12 runs, from the cells of it that were read;
    None when the row holds no word at all. The row's cells sit on one line, so a cell the
    text layer left empty belongs in the same band as the cells beside it."""
    words = [w for cell in cells for w in cell]
    return (min(w.top for w in words), max(w.bottom for w in words)) if words else None


def _place(
    stacks: Mapping[str, Sequence[tuple[Word, ...]]], top: float, floor: float, count: int
) -> dict[str, dict[int, tuple[Word, ...]]] | None:
    """Which row of block 12 each cell belongs to, column by column; None when the cells
    cannot be placed.

    A column holding a cell for every row is read by rank: its k-th cell down is row k.
    Where OCR read fewer cells, as it does to a row of zeroes, the rows between them are
    counted off in steps of how far apart the rows are, which is the median step the cells
    themselves show; which row such a column starts on is then one rounding against the
    block's own height. Either way the cells have to sit evenly afterwards, so a cell one
    row out of place is refused rather than reported as another row's period of service.
    """
    band = (floor - top) / count  # one row's share of the block's height
    if band <= 0:
        return None
    centres = {name: [_centre(cell) for cell in cells] for name, cells in stacks.items()}
    steps = [b - a for cys in centres.values() for a, b in pairwise(cys)]
    pitch = statistics.median(steps) if steps else band
    placed: dict[str, dict[int, tuple[Word, ...]]] = {}
    for name, cells in stacks.items():
        cys = centres[name]
        if not cys:
            placed[name] = {}
            continue
        if len(cys) == count:
            index = list(range(count))
        else:
            apart = list(accumulate((round((b - a) / pitch) for a, b in pairwise(cys)), initial=0))
            origin = statistics.median(cy - n * pitch for cy, n in zip(cys, apart, strict=True))
            index = [round((origin - top) / pitch - 0.5) + n for n in apart]
        # A cell below the last row belongs to whatever sits under the block, not to a row.
        keep = [(i, cy, cell) for i, cy, cell in zip(index, cys, cells, strict=True) if i < count]
        rows = [i for i, _, _ in keep]
        if not rows or rows[0] < 0 or rows != sorted(set(rows)):
            return None
        if not _even([cy for _, cy, _ in keep], rows, band):
            return None
        placed[name] = {i: cell for i, _, cell in keep}
    return placed


def _even(cys: Sequence[float], index: Sequence[int], band: float) -> bool:
    """Whether cells at heights `cys`, read as rows `index`, sit evenly one row apart: a
    line through them passes within half a row of every one. Its slope is how far apart the
    rows are, and has to be about one band, or these are not the block's rows."""
    if len(cys) < 2:
        return True
    middle = statistics.mean(index)
    pitch = sum((i - middle) * cy for i, cy in zip(index, cys, strict=True)) / sum(
        (i - middle) ** 2 for i in index
    )
    if not PITCH_OF_BAND[0] * band <= pitch <= PITCH_OF_BAND[1] * band:
        return False
    rows = list(zip(cys, index, strict=True))
    origin = statistics.median(cy - i * pitch for cy, i in rows)  # where row a sits
    return all(abs(cy - origin - i * pitch) <= pitch / 2 for cy, i in rows)


def _headings(words: Iterable[Word], anchor: _Label) -> dict[str, Word] | None:
    """The word that reads as each of block 12's column headings; None if one is missing."""
    words = list(words)
    found: dict[str, Word] = {}
    used: set[int] = set()
    for name in COLUMNS:
        best = _heading(name, [w for w in words if id(w) not in used], anchor)
        if best is None:
            return None
        found[name] = best[1]
        used.add(id(best[1]))
    return found


def _heading(name: str, words: Iterable[Word], anchor: _Label | None) -> tuple[float, Word] | None:
    """(score, word) for the word that best reads as block 12's column heading `name`. With
    block 12's label or its first row label as `anchor`, only words right of it count,
    nearest first, so "years" in block 11's own label is not taken for the heading."""
    near = (anchor.x0, anchor.top) if anchor else (0.0, 0.0)
    scored = [
        (score, w)
        for w in words
        if (score := fuzz.ratio(name, _squash_text(w.text))) >= HEADING_MATCH
        and (anchor is None or w.x0 > anchor.x0)
    ]
    return max(
        scored, key=lambda sw: (sw[0], -math.dist((sw[1].x0, sw[1].top), near)), default=None
    )


def _columns(headings: Mapping[str, Word]) -> dict[str, tuple[float, float]]:
    """Each column's left and right edge: its heading's centre, as wide as the median gap
    between neighbouring headings."""
    centres = [_cx(headings[name]) for name in COLUMNS]
    width = statistics.median(b - a for a, b in pairwise(centres))
    return {
        name: (centre - width / 2, centre + width / 2)
        for name, centre in zip(COLUMNS, centres, strict=True)
    }


def _stack(words: Sequence[Word], tol: float) -> list[tuple[Word, ...]]:
    """One column's words grouped into the cells they sit in, top to bottom. A cell's words
    sit on one line, so they are grouped by the height of their centres."""
    groups: list[list[Word]] = []
    for w in sorted(words, key=_cy):
        if groups and _cy(w) - _cy(groups[-1][-1]) <= tol:
            groups[-1].append(w)
        else:
            groups.append([w])
    return [tuple(sorted(group, key=lambda w: w.x0)) for group in groups]


def _centre(words: Iterable[Word]) -> float:
    """How far down the page one cell's words sit, on average."""
    return statistics.mean(_cy(w) for w in words)


def _record_lines(edition: Edition, cells: Sequence[Cell]) -> list[str]:
    """Block 12's rows read, one line each: the row label, then 'YYYY MM DD'."""
    lines = []
    for row in edition.rows:
        row_cells = [c for c in cells if c.row == row.letter]
        if row_cells and all(c.status is Status.READ for c in row_cells):
            lines.append(
                f"{row.letter.upper()}. {row.label} {' '.join(c.value for c in row_cells)}"
            )
    return lines


def _record_check(edition: Edition, cells: Sequence[Cell]) -> list[str]:
    """A note when the net active service read does not follow from the dates it sits
    between. The form counts that period inclusively, and withholds time lost (block 29),
    so a difference is reported rather than corrected."""
    read = {
        row.letter: [int(c.value) for c in cells if c.row == row.letter and c.status is Status.READ]
        for row in edition.rows
    }
    if any(len(read[letter]) != 3 for letter in (ENTERED, SEPARATED, NET_ACTIVE)):
        return []
    try:
        entered, separated = (date(*read[letter]) for letter in (ENTERED, SEPARATED))
    except ValueError:  # pragma: no cover - a read row is already a possible date
        return []
    years, months, days = read[NET_ACTIVE]
    off = (separated - _advance(entered, 12 * years + months, days - 1)).days
    if abs(off) <= RECORD_DAYS_SLACK:
        return []
    net = next(row for row in edition.rows if row.letter == NET_ACTIVE)
    return [
        f"Block {edition.record}{NET_ACTIVE} ({net.label.lower()}) is {abs(off)} days "
        f"{'short of' if off > 0 else 'longer than'} the period between the dates in "
        f"{edition.record}{ENTERED} and {edition.record}{SEPARATED}; the form's own figure "
        "is used (time lost is not read)."
    ]


def _advance(start: date, months: int, days: int) -> date:
    """`start` plus whole calendar months, then days, as the form counts service."""
    carry, month = divmod(start.month - 1 + months, 12)
    year = start.year + carry
    day = min(start.day, monthrange(year, month + 1)[1])
    return date(year, month + 1, day) + timedelta(days=days)


def _cell(words: Iterable[Word]) -> str:
    return "".join(w.text for w in words)


def _digits(cell: str, width: int) -> str:
    """A numeric cell with OCR's usual confusions undone: O/o/Q/D for 0, l/I/| for 1, "()"
    for 0, N for 0 in a two-digit cell, S for 5 when every other character is a digit, and
    stray punctuation dropped. A cell of this block holds digits and nothing else, so a
    letter in one is a digit misread."""
    s = ZERO_BRACKETS_RE.sub("0", cell)
    s = re.sub(r"[^0-9A-Za-z|]", "", s).translate(OCR_DIGITS)
    if width == 2:  # the form prints "00", which OCR runs together as "NO" or "N0"
        s = s.replace("N", "0").replace("n", "0")
    if s.replace("S", "").isdigit():
        s = s.replace("S", "5")
    return s


def _cell_digits(text: str, width: int, box: Box, page_scan: Callable[[], _Page]) -> _Read:
    """A cell's `width` digits, or None, and what came of reading it again from the page.

    A cell the text layer did not leave as digits is cut out of the page image and read
    again, at each margin and magnification in REREAD_TRIES until one reads as digits.
    """
    if (digits := _of_width(text, width)) is not None:
        return _Read(digits)
    found = page_scan()
    if found.scan is None:
        return _Read(None, missing_tools=found.missing_tools)
    attempt = None
    for how in REREAD_TRIES:
        read = _reread(found.scan, box, how)
        if read is None:
            return _Read(None, attempt, missing_tools=True)
        crop, text = read
        digits = _of_width(text, width)
        attempt = Reread(crop, how.zoom, shape(text) if text else "none", digits is not None)
        if digits is not None:
            return _Read(digits, attempt)
    return _Read(None, attempt)


def _of_width(text: str, width: int) -> str | None:
    digits = _digits(text, width)
    return digits if digits.isdigit() and len(digits) == width else None


def _reread(scan: Scan, box: Box, how: Try) -> tuple[Box, str] | None:
    """One cell's box, cut out of the page image as `how` says and read again as digits and
    nothing else, with the box it was cut at in the image's own pixels. None when the `ocr`
    extra or the tesseract binary is not installed."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:  # pragma: no cover - optional dependency
        return None
    pads = (-how.pad, -how.pad, how.pad, how.pad)
    crop = tuple(float(int((v + p) * scan.scale)) for v, p in zip(box, pads, strict=True))
    image = scan.image.crop(tuple(int(v) for v in crop))
    if how.black_and_white:
        image = image.convert("L").point(lambda grey: 0 if grey < DARK else 255)
    if how.zoom != 1.0:
        size = (max(1, int(image.width * how.zoom)), max(1, int(image.height * how.zoom)))
        image = image.resize(size, Image.Resampling.LANCZOS)
    try:
        config = f"--psm {how.psm} {CELL_DIGIT_WHITELIST}"
        return crop, pytesseract.image_to_string(image, config=config).strip()
    except (OSError, RuntimeError):  # pragma: no cover - tesseract missing or failing
        return None


def _scan_page(scan: ScanPages | None, page: int) -> _Page:
    """Page `page` of the scan behind the file, rendered on the first call. A page that is
    not a scan has no image to read again; a page that is one has none here when the `ocr`
    extra is not installed, which installing it would fix."""
    if scan is None:
        return _Page()
    try:
        pages = scan()
    except ExtractionError:  # pragma: no cover - the 'ocr' extra is not installed
        return _Page(missing_tools=True)
    return _Page(pages[page]) if page < len(pages) else _Page()


def _row_value(digits: Sequence[str | None], is_date: bool) -> str | None:
    """'YYYY MM DD' when the three cells hold a possible value; None rather than a guess."""
    if any(d is None for d in digits):
        return None
    y, m, d = (int(v) for v in digits)
    if is_date:
        try:
            date(y, m, d)
        except ValueError:
            return None
    elif y > MAX_SERVICE_YEARS or m > 12 or d > 31:
        return None
    return " ".join(digits)
