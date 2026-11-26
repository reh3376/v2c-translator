"""Print where things sit on a DD-214 page, with no text from it, so its layout can be shared.

The layout reader (`extractors/dd214_layout.py`) boxes each block from its printed label.
To fit it to a real form we need that form's geometry, but not its contents. This module
prints the geometry alone:

- each printed form label it finds, named by our id for it (`L4a`), never by its text;
- every other word as its box and a shape code (`A5` is five letters);
- the text lines the PDF's text layer or OCR holds, as boxes with word counts;
- the page's ruled lines, from the PDF's drawing or found in the scanned image;
- the boxes the layout reader drew, and what it did with each, with no values.

`write_png()` draws the same geometry as rectangles and lines on a blank canvas. It is
never given the page image.
"""

from __future__ import annotations

import math
import re
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .extract import IMAGE_SUFFIXES, ExtractionError, Word, load_text, render_scan
from .extractors.dd214_layout import (
    COLUMNS,
    EDITION_2000,
    Box,
    Form,
    _assign,
    _head,
    _heading,
    _reading_lines,
    read_form,
)

HEADER = (
    "# dd214kw inspect-layout: geometry only; contains no text from your document.",
    "# Each word is its box and a shape code: D digits, A letters, M mixed, P punctuation,",
    "# then its length. Labels are our ids for the form's printed labels: L4a is block 4a's.",
    "# Boxes are x0 top x1 bottom, from the page's top left corner.",
    "# Look this file over before you share it.",
)

# The printed labels of the AUG 2009 and 2000 forms, by our id for each.
LABELS: tuple[tuple[str, str], ...] = (
    ("Ltitle", EDITION_2000.title),
    ("Lform", "DD FORM 214"),
    *((f"L{block}", block + _head(text)) for block, text in EDITION_2000.labels),
    *((f"L12{row.letter}", row.letter + row.label) for row in EDITION_2000.rows),
    ("Lspecial", "SPECIAL ADDITIONAL INFORMATION"),
)
# Block 12's column headings are single words, so they are matched word by word.
HEADINGS = (("L12yr", "YEARS"), ("L12mo", "MONTHS"), ("L12dy", "DAYS"))
LABEL_IDS = (*dict.fromkeys(key for key, _ in LABELS), *(key for key, _ in HEADINGS))
COLUMN_IDS = dict(zip(COLUMNS, ("yr", "mo", "dy"), strict=True))
PNG_SIDE = 1600  # pixels along the page's longer side


@dataclass(frozen=True, slots=True)
class Rule:
    """A ruled line, from end to end."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def vertical(self) -> bool:
        return abs(self.y1 - self.y0) > abs(self.x1 - self.x0)


@dataclass(frozen=True, slots=True)
class Run:
    """One line of the text layer as pdfminer groups it, or one line of OCR."""

    box: Box
    words: int


@dataclass(frozen=True, slots=True)
class Page:
    number: int
    width: float
    height: float
    lines: tuple[tuple[Word, ...], ...]  # the page's words in the order their source gives
    runs: tuple[Run, ...]
    rules: tuple[Rule, ...]
    rule_source: str  # "drawn", "image" or "absent"


@dataclass(frozen=True, slots=True)
class Label:
    id: str
    page: int
    score: float
    words: tuple[Word, ...]

    @property
    def box(self) -> Box:
        return _bounds(self.words)


@dataclass(frozen=True, slots=True)
class Inspection:
    source: str  # "text-layer" or "ocr"
    unit: str  # "pt" or "px"
    pages: tuple[Page, ...]
    labels: tuple[Label, ...]
    form: Form  # what the layout reader did with the page


def inspect(path: Path, *, ocr: bool = False) -> Inspection:
    """`path`'s geometry: words loaded exactly as the reader loads them."""
    content = load_text(path, ocr=ocr)
    if not content.words:
        raise ExtractionError("The file has no positioned words: nothing to inspect.")
    if content.lines:
        images = _ocr_images(path)
        pages = tuple(_ocr_page(n, img, content.lines) for n, img in enumerate(images))
        source, unit = "ocr", "px"
    else:
        pages = _pdf_pages(path, content.words)
        source, unit = "text-layer", "pt"
    labels = tuple(lb for page in pages for lb in _labels(page))
    form = read_form(content.words, content.lines, content.scan)
    return Inspection(source, unit, pages, labels, form)


# --------------------------------------------------------------------------- report


def report(ins: Inspection) -> list[str]:
    """The inspection as lines of text. Every line is a fixed header line or one of the
    shapes in `tests/test_inspect_layout.py`'s grammar: ids, boxes, counts and scores."""
    out = [*HEADER, f"source {ins.source}", f"pages {len(ins.pages)}"]
    out += [f"page {p.number} size {_n(p.width)} {_n(p.height)} unit {ins.unit}" for p in ins.pages]
    out.append("[labels]")
    for lb in ins.labels:
        out.append(f"label {lb.id} page {lb.page} score {lb.score:.1f} bbox {_box(lb.box)}")
    for page in ins.pages:
        found = {lb.id for lb in ins.labels if lb.page == page.number}
        out += [f"missing {key} page {page.number}" for key in LABEL_IDS if key not in found]
    out.append("[words]")
    labelled = {id(w) for lb in ins.labels for w in lb.words}
    for page in ins.pages:
        for i, line in enumerate(page.lines):
            if words := [w for w in line if id(w) not in labelled]:
                masked = " | ".join(f"{_box(_bounds([w]))} {shape(w.text)}" for w in words)
                out.append(f"line {i} page {page.number} | {masked}")
    out.append("[runs]")
    for page in ins.pages:
        verticals = [r for r in page.rules if r.vertical]
        for run in page.runs:
            crosses = sum(_crosses(run.box, rule) for rule in verticals)
            out.append(
                f"run page {page.number} bbox {_box(run.box)} words {run.words} crosses {crosses}"
            )
    out.append("[rules]")
    for page in ins.pages:
        out.append(f"rules page {page.number} source {page.rule_source} count {len(page.rules)}")
        for r in page.rules:
            kind = "v" if r.vertical else "h"
            out.append(f"rule page {page.number} {kind} {_box((r.x0, r.y0, r.x1, r.y1))}")
    out.append("[reader]")
    out += _reader(ins.form)
    return out


def _reader(form: Form) -> list[str]:
    """The reader's boxes and what it did with each. No value, only boxes and statuses."""
    layout = form.layout
    if layout is None:
        return ["reader line-order"]
    out = [f"reader position page {layout.page}"]
    for r in layout.regions:
        box = f" bbox {_box(r.box)}" if r.box else ""
        out.append(f"block B{r.block} status {r.status}{box}")
    for c in layout.cells:
        line = f"cell B12{c.row} {COLUMN_IDS[c.column]} status {c.status}"
        if c.box:
            line += f" bbox {_box(c.box)} words {len(c.words)}"
            if c.words:
                line += f" shape {shape(''.join(w.text for w in c.words))}"
        out.append(line)
    return out


def shape(text: str) -> str:
    """A word's shape code: its kind of characters and its length, never a character."""
    if all(c.isdigit() for c in text):
        kind = "D"
    elif all(c.isalpha() for c in text):
        kind = "A"
    elif not any(c.isalnum() for c in text):
        kind = "P"
    else:
        kind = "M"
    return f"{kind}{len(text)}"


def _n(v: float) -> str:
    return f"{v:.1f}"


def _box(box: Box) -> str:
    return " ".join(map(_n, box))


def _bounds(words: Iterable[Word]) -> Box:
    words = list(words)
    return (
        min(w.x0 for w in words),
        min(w.top for w in words),
        max(w.x1 for w in words),
        max(w.bottom for w in words),
    )


def _crosses(box: Box, rule: Rule) -> bool:
    """Whether a text line's box runs across a vertical rule."""
    x0, top, x1, bottom = box
    x = (rule.x0 + rule.x1) / 2
    return x0 + 1 < x < x1 - 1 and min(rule.y0, rule.y1) < bottom and max(rule.y0, rule.y1) > top


# --------------------------------------------------------------------------- picture

# Each kind of shape has one colour, drawn flat: the picture holds these colours and no other.
PALETTE = {
    "canvas": (255, 255, 255),
    "word": (190, 190, 190),
    "rule": (230, 120, 0),
    "reader": (0, 80, 220),
    "label": (0, 130, 0),
}


def write_png(ins: Inspection, path: Path) -> None:
    """Draw one page's geometry on a blank canvas: words as grey boxes, the rules, the
    reader's boxes tagged with their block, and the labels tagged with their ids. The page
    image is never drawn: this only knows boxes, lines and our ids."""
    from PIL import Image, ImageDraw, ImageFont

    page = _focus(ins)
    scale = PNG_SIDE / max(page.width, page.height)
    size = (math.ceil(page.width * scale), math.ceil(page.height * scale))
    img = Image.new("RGB", size, PALETTE["canvas"])
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default_imagefont()  # a bitmap font: no blended edge colours

    def px(box: Box) -> Box:
        x0, y0, x1, y1 = (v * scale for v in box)
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

    labels = [lb for lb in ins.labels if lb.page == page.number]
    labelled = {id(w) for lb in labels for w in lb.words}
    for w in (w for line in page.lines for w in line if id(w) not in labelled):
        draw.rectangle(px(_bounds([w])), fill=PALETTE["word"])
    for r in page.rules:
        draw.line(px((r.x0, r.y0, r.x1, r.y1)), fill=PALETTE["rule"], width=2)
    layout = ins.form.layout
    if layout is not None and layout.page == page.number:
        for c in layout.cells:
            if c.box:
                draw.rectangle(px(c.box), outline=PALETTE["reader"])
        for region in layout.regions:
            if region.box:
                x0, _, _, y1 = box = px(region.box)
                draw.rectangle(box, outline=PALETTE["reader"], width=2)
                draw.text((x0 + 3, y1 - 13), f"B{region.block}", fill=PALETTE["reader"], font=font)
    for lb in labels:
        x0, y0, _, _ = box = px(lb.box)
        draw.rectangle(box, outline=PALETTE["label"])
        draw.text((x0, max(0, y0 - 11)), lb.id, fill=PALETTE["label"], font=font)
    img.save(path, "PNG")


def _focus(ins: Inspection) -> Page:
    """The page the reader read, or else the page with the most labels found."""
    if ins.form.layout is not None:
        return ins.pages[ins.form.layout.page]
    return max(ins.pages, key=lambda p: sum(lb.page == p.number for lb in ins.labels))


# --------------------------------------------------------------------------- labels


def _labels(page: Page) -> list[Label]:
    """The form's printed labels found on `page`, by our id. No word belongs to two. The
    page's own lines are matched, as the reader matches them."""
    words = [w for line in page.lines for w in line]
    found = _assign(page.lines, list(LABELS)) if words else {}
    labels = [Label(key, page.number, lb.score, lb.words) for key, lb in found.items()]
    used = {id(w) for lb in labels for w in lb.words}
    anchor = found.get("L12a") or found.get("L12")
    for key, name in HEADINGS:
        if best := _heading(name, [w for w in words if id(w) not in used], anchor):
            score, word = best
            labels.append(Label(key, page.number, score, (word,)))
            used.add(id(word))
    return sorted(labels, key=lambda lb: LABEL_IDS.index(lb.id))


# --------------------------------------------------------------------------- text layer


def _pdf_pages(path: Path, words: Sequence[Word]) -> tuple[Page, ...]:
    """Each page of a PDF read from its text layer: its size, its words in the text layer's
    order cut into lines, pdfminer's text lines, and its ruled lines."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTContainer, LTCurve, LTImage, LTRect, LTTextLine

    def walk(item):
        yield item
        if isinstance(item, LTContainer) and not isinstance(item, LTTextLine):
            for child in item:
                yield from walk(child)

    pages = []
    for n, layout in enumerate(extract_pages(path, laparams=LAParams(all_texts=True))):
        h = layout.height

        def flip(bbox, h=h) -> Box:
            x0, y0, x1, y1 = bbox
            return x0, h - y1, x1, h - y0

        items = list(walk(layout))
        runs = tuple(
            Run(flip(o.bbox), len(o.get_text().split()))
            for o in items
            if isinstance(o, LTTextLine) and o.get_text().strip()
        )
        rules = _drawn_rules(
            [(flip(o.bbox), isinstance(o, LTRect)) for o in items if isinstance(o, LTCurve)]
        )
        source = "drawn"
        if not rules:
            images = [o for o in items if isinstance(o, LTImage)]
            scan = max(images, key=lambda o: o.width * o.height, default=None)
            rules = _scan_rules(path, n, scan, flip(scan.bbox)) if scan else ()
            source = "image" if rules else "absent"
        page_words = [w for w in words if w.page == n]
        pages.append(
            Page(n, layout.width, h, tuple(_reading_lines(page_words)), runs, rules, source)
        )
    return tuple(pages)


def _drawn_rules(curves: Iterable[tuple[Box, bool]]) -> tuple[Rule, ...]:
    """Lines and rectangles the PDF draws, as horizontal and vertical rules: a thin shape is
    one rule, a rectangle its four sides. Other curves are left out."""
    rules = set()
    for box, is_rect in curves:
        x0, top, x1, bottom = (round(v, 1) for v in box)
        if bottom - top <= 2:
            rules.add((x0, (top + bottom) / 2, x1, (top + bottom) / 2))
        elif x1 - x0 <= 2:
            rules.add(((x0 + x1) / 2, top, (x0 + x1) / 2, bottom))
        elif is_rect:
            rules |= {(x0, top, x1, top), (x0, bottom, x1, bottom)}
            rules |= {(x0, top, x0, bottom), (x1, top, x1, bottom)}
    return tuple(Rule(*r) for r in sorted(rules))


def _scan_rules(path: Path, page: int, scan, box: Box) -> tuple[Rule, ...]:
    """The ruled lines in a page's scanned image, placed where the PDF draws the image."""
    from pypdf import PdfReader

    objid = getattr(scan.stream, "objid", None)
    try:
        img = next(
            (
                im.image
                for im in PdfReader(path).pages[page].images
                if im.indirect_reference is not None and im.indirect_reference.idnum == objid
            ),
            None,
        )
    except Exception:  # pypdf cannot decode it: there are no rules to find
        return ()
    if img is None:
        return ()
    x0, top, x1, bottom = box
    # A rotated or stretched placement would need its matrix; leave such an image out.
    if abs(math.log((img.width / img.height) / ((x1 - x0) / (bottom - top)))) > 0.05:
        return ()
    sx, sy = (x1 - x0) / img.width, (bottom - top) / img.height
    return tuple(
        Rule(x0 + a * sx, top + b * sy, x0 + c * sx, top + d * sy)
        for a, b, c, d in _image_rules(img)
    )


# --------------------------------------------------------------------------- OCR


def _ocr_images(path: Path) -> list:
    """The images OCR read: an image file itself, or a scan rendered as the reader renders it."""
    if path.suffix.lower() in IMAGE_SUFFIXES:
        from PIL import Image

        return [Image.open(path)]
    return render_scan(path)


def _ocr_page(n: int, img, lines: Sequence[tuple[Word, ...]]) -> Page:
    """A page read by OCR: the image's size in pixels, OCR's own lines, and the image's rules."""
    mine = tuple(line for line in lines if line[0].page == n)
    runs = tuple(Run(_bounds(line), len(line)) for line in mine)
    rules = tuple(Rule(*map(float, r)) for r in _image_rules(img))
    return Page(
        n, float(img.width), float(img.height), mine, runs, rules, "image" if rules else "absent"
    )


def _image_rules(img) -> list[tuple[float, float, float, float]]:
    """Long straight runs of dark pixels, along rows and along columns, as line ends in the
    image's pixels. Only the ends leave here: no pixel does."""
    from PIL import Image

    gray = img.convert("L")
    least = max(gray.size) // 60  # about 13 points on a letter page: longer than a glyph
    dark = gray.point(lambda p: 255 if p < 128 else 0)
    w, h = dark.size
    rows = list(_strokes(dark.tobytes(), w, h, least))
    columns = dark.transpose(Image.Transpose.TRANSPOSE).tobytes()
    return rows + [(x0, a, x1, b) for a, x0, b, x1 in _strokes(columns, h, w, least)]


@dataclass(slots=True)
class _Stroke:
    segments: list[tuple[int, int, int]]  # (row, start, end)
    start: int
    end: int
    last: int  # the last row it was seen on


def _strokes(data: bytes, width: int, height: int, least: int):
    """Runs of at least `least` dark pixels along each row, joined across neighbouring rows
    into strokes, so a thick or slightly skewed line is one stroke. Yields each stroke's
    (start, row at start, end, row at end). A stroke much thicker than a ruled line, such
    as a filled area, is not a rule and is left out."""
    run = re.compile(rb"\xff{%d,}" % least)
    thick = max(3, max(width, height) // 250)
    live: list[_Stroke] = []
    done: list[_Stroke] = []
    for y in range(height):
        for m in run.finditer(data, y * width, (y + 1) * width):
            a, b = m.start() - y * width, m.end() - y * width
            s = next((s for s in live if a <= s.end + 3 and b >= s.start - 3), None)
            if s is None:
                live.append(_Stroke([(y, a, b)], a, b, y))
            else:
                s.segments.append((y, a, b))
                s.start, s.end, s.last = min(s.start, a), max(s.end, b), y
        done += [s for s in live if s.last < y - 2]
        live = [s for s in live if s.last >= y - 2]
    for s in done + live:
        length = s.end - s.start
        if length < least or sum(b - a for _, a, b in s.segments) / length > thick:
            continue
        at_start = statistics.mean(r for r, a, _ in s.segments if a <= s.start + 2)
        at_end = statistics.mean(r for r, _, b in s.segments if b >= s.end - 2)
        yield s.start, at_start, s.end, at_end
