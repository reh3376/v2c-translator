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

import re
import statistics
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from itertools import combinations, pairwise

from rapidfuzz import fuzz
from rapidfuzz.distance import Indel

from ..extract import Word
from ..parse import MAX_SERVICE_YEARS, detect_version

# Fuzzy-match floor (0-100) for a printed label against a line of OCR'd text.
LABEL_MATCH = 85
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
OCR_DIGITS = str.maketrans("OoIl|", "00111")
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
class Cell:
    """One cell of block 12's grid: a row's YEAR(S), MONTH(S) or DAY(S)."""

    row: str  # the row's letter
    column: str  # one of COLUMNS
    status: Status
    box: Box | None = None
    words: tuple[Word, ...] = ()


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


def read_form(words: Sequence[Word]) -> Form:
    """Read the DD-214 page among `words` by position: the page with the most labels found."""
    if not words:
        return Form(None)  # Plain text: no positions to read by.
    if detect_version(_text(words)) not in ("unknown", *(ed.name for ed in EDITIONS)):
        return Form(None)  # Another edition (2022): its geometry is not known here.
    pages: dict[int, list[Word]] = {}
    for w in words:
        pages.setdefault(w.page, []).append(w)
    found = max(
        ((ed, page, *_find_labels(_lines(page), ed)) for page in pages.values() for ed in EDITIONS),
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
    layout, notes = _locate(edition, page, blocks, rows, tol)
    return Form(_write(edition, layout), tuple(notes), layout)


def _locate(
    edition: Edition,
    page: list[Word],
    blocks: dict[str, _Label],
    rows: dict[str, _Label],
    tol: float,
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

    def box(block: str) -> tuple[Box, set[str], set[str]]:
        return _box(blocks[block], blocks.values(), rows.values(), right, bottom, tol)

    withheld = [Region(b, Status.WITHHELD, box(b)[0]) for b in edition.withheld if b in blocks]
    page = [w for w in page if not any(_inside(w, r.box) for r in withheld)]
    bounds = dict(edition.bounds)
    regions: list[Region] = []
    cells: list[Cell] = []
    notes: list[str] = []
    for block in edition.written:
        if block == edition.record:
            cells, row_notes = _record(edition, page, rows, tol)
            notes += row_notes
            continue
        name = _name(edition, block).lower()
        if block not in blocks:
            regions.append(Region(block, Status.NOT_FOUND))
            notes.append(f"Block {block} ({name}) was not found on the page; not read.")
            continue
        b, beside, below = box(block)
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
        regions.append(Region(block, Status.READ, b, tuple(w for w in page if _inside(w, b))))
    return Layout(page_no, (*regions, *withheld), tuple(cells)), notes


def _write(edition: Edition, layout: Layout) -> str:
    """The blocks read, as plain text in the shape `parse.segment()` reads."""
    out = [edition.title]
    regions = {r.block: r for r in layout.regions}
    for block in edition.written:
        name = _name(edition, block)
        if block == edition.record:
            out += [f"{block}. {name}", *_record_lines(edition, layout.cells)]
            continue
        if regions[block].status is not Status.READ:
            continue
        lines = _drop_label(_lines(regions[block].words), block + _printed(edition, block))
        text = [SPLIT_SEPARATOR_RE.sub("//", _text(line)) for line in lines]
        # With "//" between entries, a line break in the box is only a wrap.
        out += [f"{block}. {name}", *([" ".join(text)] if any("//" in t for t in text) else text)]
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
    """Best match for each (key, text) in `lines`, greedily by score, no word used twice."""
    candidates = []
    for line in lines:
        squashed, owner = _squash(line)
        size = Counter(owner)
        for key, text in wanted:
            score, span = _match(_squash_text(text), squashed)
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


def _drop_label(lines: list[tuple[Word, ...]], label: str) -> list[tuple[Word, ...]]:
    """The box's lines after its printed label, which may wrap onto several lines."""
    target = _squash_text(label)
    k = max(
        range(1, len(lines) + 1),
        key=lambda k: fuzz.ratio(target, _squash(w for line in lines[:k] for w in line)[0]),
        default=0,
    )
    return lines[k:]


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


# --------------------------------------------------------------------------- geometry


def _cx(w: Word) -> float:
    return (w.x0 + w.x1) / 2


def _cy(w: Word) -> float:
    return (w.top + w.bottom) / 2


def _text_height(words: Sequence[Word]) -> float:
    return statistics.median(w.bottom - w.top for w in words)


def _lines(words: Sequence[Word]) -> list[tuple[Word, ...]]:
    """Words grouped into visual lines, top to bottom, each left to right. A line is
    followed word by word, so a skewed scan's lines, which drift as they cross the page,
    stay whole."""
    if not words:
        return []
    tol = 0.5 * _text_height(words)
    lines: list[list[Word]] = []
    for w in sorted(words, key=lambda w: w.x0):
        near = min(lines, key=lambda line: abs(_cy(line[-1]) - _cy(w)), default=None)
        if near and abs(_cy(near[-1]) - _cy(w)) <= tol and near[-1].x0 < w.x0:
            near.append(w)
        else:
            lines.append([w])
    return [tuple(line) for line in sorted(lines, key=lambda line: _cy(line[0]))]


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
    edition: Edition, page: list[Word], rows: dict[str, _Label], tol: float
) -> tuple[list[Cell], list[str]]:
    """Block 12 boxed as a grid: rows from the row labels' heights, columns from the
    YEAR(S)/MONTH(S)/DAY(S) headings above them."""
    block = edition.record
    unboxed = [Cell(row.letter, col, Status.NOT_FOUND) for row in edition.rows for col in COLUMNS]
    found = {
        i: statistics.mean(_cy(w) for w in rows[row.letter].words)
        for i, row in enumerate(edition.rows)
        if row.letter in rows
    }
    order = sorted(found)
    steps = [(found[j] - found[i]) / (j - i) for i, j in pairwise(order)]
    if not steps:
        return unboxed, [f"Block {block}'s rows were not found; not read."]
    pitch = statistics.median(steps)
    first = statistics.median(found[i] - i * pitch for i in order)  # where row a sits
    # The rows are evenly spaced, so a row whose label OCR missed sits between its neighbours.
    centres = {i: found.get(i, first + i * pitch) for i in range(order[0], order[-1] + 1)}
    left = min(lb.x0 for lb in rows.values()) - tol
    words = [w for w in page if _cx(w) >= left and first - 3 * pitch <= _cy(w)]

    headings = []
    above = [w for w in words if _cy(w) < first - pitch / 2]
    for name in COLUMNS:
        best = max(above, key=lambda w: fuzz.ratio(name, _squash_text(w.text)), default=None)
        if best is None or fuzz.ratio(name, _squash_text(best.text)) < 75:
            return unboxed, [
                f"Block {block}'s YEAR(S)/MONTH(S)/DAY(S) headings were not found; not read."
            ]
        headings.append(_cx(best))
    width = statistics.median(b - a for a, b in pairwise(headings))
    columns = [(c - width / 2, c + width / 2) for c in headings]

    cells, notes = [], []
    words.sort(key=lambda w: w.x0)
    for i, row in enumerate(edition.rows):
        name = f"block {block}{row.letter} ({row.label.lower()})"
        if i not in centres:
            notes.append(f"The label of {name} was not found; not read.")
            cells += [Cell(row.letter, col, Status.NOT_FOUND) for col in COLUMNS]
            continue
        top, bottom = centres[i] - pitch / 2, centres[i] + pitch / 2
        boxes = [(x0, top, x1, bottom) for x0, x1 in columns]
        inside = [tuple(w for w in words if _inside(w, box)) for box in boxes]
        status = Status.READ if _row_value(map(_cell, inside), row.is_date) else Status.REFUSED
        if status is Status.REFUSED:
            notes.append(f"The value of {name} could not be read; not used.")
        cells += [
            Cell(row.letter, col, status, box, ws)
            for col, box, ws in zip(COLUMNS, boxes, inside, strict=True)
        ]
    return cells, notes


def _record_lines(edition: Edition, cells: Sequence[Cell]) -> list[str]:
    """Block 12's rows read, one line each: the row label, then 'YYYY MM DD'."""
    lines = []
    for row in edition.rows:
        row_cells = [c for c in cells if c.row == row.letter]
        if all(c.status is Status.READ for c in row_cells):
            value = _row_value((_cell(c.words) for c in row_cells), row.is_date)
            lines.append(f"{row.letter.upper()}. {row.label} {value}")
    return lines


def _cell(words: Iterable[Word]) -> str:
    return "".join(w.text for w in words)


def _digits(cell: str) -> str:
    """A numeric cell with OCR's usual confusions undone: O/o for 0, l/I/| for 1, S for 5
    when every other character is a digit, and stray punctuation dropped."""
    s = re.sub(r"[^0-9A-Za-z|]", "", cell).translate(OCR_DIGITS)
    if s.replace("S", "").isdigit():
        s = s.replace("S", "5")
    return s


def _row_value(cells: Iterable[str], is_date: bool) -> str | None:
    """'YYYY MM DD' when the three cells hold a possible value; None rather than a guess."""
    digits = [_digits(c) for c in cells]
    if not all(d.isdigit() for d in digits) or tuple(map(len, digits)) != CELL_DIGITS:
        return None
    y, m, d = map(int, digits)
    if is_date:
        try:
            date(y, m, d)
        except ValueError:
            return None
    elif y > MAX_SERVICE_YEARS or m > 12 or d > 31:
        return None
    return " ".join(digits)
