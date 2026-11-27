"""Get raw text out of a DD-214 file (text, PDF with a text layer, or scanned image/PDF).

For a PDF or an image, also where each word sits on the page, so a form's side-by-side
blocks can be read by position instead of by line order.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
TESSERACT_CONFIG = "--psm 4"

# One OCR thread per process, unless the caller asked for more.
#
# Tesseract's OpenMP parallelism spends more time spin-waiting than reading. Measured in
# the container on a 2-core box with `deploy/measure.sh`, a 5-page 300 dpi scan takes 19 s
# of wall time and 17 s of CPU with one thread, and 39-58 s of wall time and 38-68 s of
# CPU with two, for the same words out: the second thread costs time and buys nothing. A
# server that runs two translations at once wants that core for the other visitor anyway,
# and `docs/deploy.md` sizes it that way.
OCR_THREADS = "1"


class ExtractionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Word:
    """One word and its box. Units are the page's own: points for a PDF text layer,
    pixels for OCR. `top` and `bottom` count down from the top edge."""

    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    page: int


@dataclass(frozen=True, slots=True)
class Scan:
    """One page of a scan as an image, with the pixels it holds per unit of that page's word
    boxes, so a word's own box can be cut out of the image and read again."""

    image: object
    scale: float


# A file's pages as images, rendered on the first call and only if something needs them.
ScanPages = Callable[[], Sequence[Scan]]


@dataclass(frozen=True, slots=True)
class Content:
    """A file's text in line order, and its words with their boxes (none for plain text).
    For OCR, also the lines tesseract put the words in; a text layer has none here.
    `scan` is set when the pages are scanned images, so a garbled word can be read again."""

    text: str
    words: tuple[Word, ...] = ()
    lines: tuple[tuple[Word, ...], ...] = ()
    scan: ScanPages | None = None


def page_count(path: Path) -> int:
    """How many pages a file holds, from a PDF's page tree. Nothing is rendered or read.

    Anything that is not a PDF is one page: an image is one, and a text file has none
    worth counting.
    """
    if path.suffix.lower() != ".pdf":
        return 1
    from pypdf import PdfReader

    return len(PdfReader(path).pages)


def load_text(path: Path, *, ocr: bool = False, max_pages: int | None = None) -> Content:
    if max_pages is not None:
        pages = page_count(path)
        if pages > max_pages:
            # Before OCR, which is what the limit is for: rendering and reading a page is
            # the expensive part, and counting pages is not.
            raise ExtractionError(f"too many pages: {pages} (limit {max_pages})")
    suffix = path.suffix.lower()
    if suffix in {".txt", ".text", ".md"}:
        return Content(path.read_text(encoding="utf-8", errors="replace"))
    if suffix == ".pdf":
        return _pdf_content(path, ocr=ocr)
    if suffix in IMAGE_SUFFIXES:
        return _ocr_images([_open_image(path)])
    raise ExtractionError(f"Unsupported file type: {suffix} (use .pdf, .txt, or an image)")


def _pdf_content(path: Path, *, ocr: bool) -> Content:
    from pypdf import PdfReader

    reader = PdfReader(path)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)

    # Fillable PDFs: field values may not be in the content stream.
    fields = reader.get_fields() or {}
    values = [
        f"{name}: {f.get('/V')}"
        for name, f in fields.items()
        if f.get("/V") not in (None, "", "/Off")
    ]
    if values:
        text += "\n" + "\n".join(values)

    if len(re.sub(r"\s", "", text)) >= 100:
        # Field values have no word boxes, so a filled form keeps to its text alone.
        if values:
            return Content(text)
        dpi = _scan_dpi(reader) if _page_images(reader.pages[0]) else 0
        return Content(text, _pdf_words(path), scan=_scan_pages(path, dpi) if dpi else None)
    if not ocr:
        raise ExtractionError(
            "PDF has no usable text layer (probably a scan). Re-run with --ocr "
            "(requires `uv sync --extra ocr` plus the tesseract and poppler binaries)."
        )
    return _ocr_images(render_scan(path))


def render_scan(path: Path) -> list:
    """A scanned PDF's pages as images, for OCR, at the resolution it was scanned at."""
    from pypdf import PdfReader

    try:
        from pdf2image import convert_from_path
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ExtractionError("OCR needs the 'ocr' extra: uv sync --extra ocr") from e
    return convert_from_path(str(path), dpi=_scan_dpi(PdfReader(path)))


def _scan_pages(path: Path, dpi: int) -> ScanPages:
    """`path`'s pages as images, rendered once, however often they are asked for."""

    @cache
    def pages() -> tuple[Scan, ...]:
        return tuple(Scan(image, dpi / 72) for image in render_scan(path))

    return pages


def _page_images(page) -> list:
    """The images a PDF page draws. A page that draws one is a scan, not a typed page."""
    return [
        x.get_object()
        for x in (page["/Resources"].get("/XObject") or {}).values()
        if x.get_object().get("/Subtype") == "/Image"
    ]


def _scan_dpi(reader) -> int:
    """The resolution the first page was scanned at, up to 300 dpi. Rendering a 200 dpi
    scan at 300 dpi resamples it, and tesseract then misreads more of it."""
    page = reader.pages[0]
    images = _page_images(page)
    if not images:
        return 300
    pixels = max(max(int(x["/Width"]), int(x["/Height"])) for x in images)
    inches = max(float(page.mediabox.width), float(page.mediabox.height)) / 72
    return max(150, min(300, round(pixels / inches)))


def _pdf_words(path: Path) -> tuple[Word, ...]:
    """Words from the text layer, each boxed by its glyphs.

    pdfminer places every glyph from the font's widths and the text state, so a text run
    that crosses a block's rule (as an OCR layer's line-long runs do) still splits there.
    """
    from pdfminer.converter import PDFPageAggregator
    from pdfminer.layout import LTChar, LTContainer
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
    from pdfminer.pdfpage import PDFPage

    def glyphs(item):
        if isinstance(item, LTChar):
            yield item
        elif isinstance(item, LTContainer):
            for child in item:
                yield from glyphs(child)

    words: list[Word] = []
    resources = PDFResourceManager()
    device = PDFPageAggregator(resources, laparams=None)
    interpreter = PDFPageInterpreter(resources, device)
    with path.open("rb") as f:
        for page_no, page in enumerate(PDFPage.get_pages(f)):
            interpreter.process_page(page)
            layout = device.get_result()
            run: list[LTChar] = []
            for ch in [*glyphs(layout), None]:
                if run and (ch is None or _starts_word(run[-1], ch)):
                    words.append(
                        Word(
                            "".join(c.get_text() for c in run),
                            min(c.x0 for c in run),
                            layout.height - max(c.y1 for c in run),
                            max(c.x1 for c in run),
                            layout.height - min(c.y0 for c in run),
                            page_no,
                        )
                    )
                    run = []
                if ch is not None and ch.get_text().strip():
                    run.append(ch)
    return tuple(words)


def _starts_word(prev, ch) -> bool:
    """Whether glyph `ch` starts a new word after glyph `prev`: a space, or a jump."""
    size = max(prev.y1 - prev.y0, 1.0)
    return (
        not ch.get_text().strip()
        or abs(ch.y0 - prev.y0) > 0.3 * size
        or not -0.3 * size < ch.x0 - prev.x1 < 0.3 * size
    )


def _open_image(path: Path):
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover
        raise ExtractionError("Image input needs the 'ocr' extra: uv sync --extra ocr") from e
    return Image.open(path)


def _ocr_images(images) -> Content:
    """OCR each page once: its words with their boxes, in tesseract's lines and line order."""
    os.environ.setdefault("OMP_THREAD_LIMIT", OCR_THREADS)  # see OCR_THREADS
    try:
        import pytesseract
    except ImportError as e:  # pragma: no cover
        raise ExtractionError("OCR needs the 'ocr' extra: uv sync --extra ocr") from e
    images = list(images)
    lines: list[tuple[Word, ...]] = []
    pages: list[str] = []
    for page_no, img in enumerate(images):
        data = pytesseract.image_to_data(
            img, config=TESSERACT_CONFIG, output_type=pytesseract.Output.DICT
        )
        page: dict[tuple[int, int, int], list[Word]] = {}
        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            x, y = data["left"][i], data["top"][i]
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            page.setdefault(key, []).append(
                Word(text, x, y, x + data["width"][i], y + data["height"][i], page_no)
            )
        lines += map(tuple, page.values())
        pages.append("\n".join(" ".join(w.text for w in line) for line in page.values()))
    # OCR's boxes are already in the image's pixels, so a cell's box needs no scaling.
    scanned = tuple(Scan(img, 1.0) for img in images)
    return Content(
        "\n".join(pages),
        tuple(w for line in lines for w in line),
        tuple(lines),
        lambda: scanned,
    )
