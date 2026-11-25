"""Get raw text out of a DD-214 file (text, PDF with a text layer, or scanned image/PDF).

For a PDF or an image, also where each word sits on the page, so a form's side-by-side
blocks can be read by position instead of by line order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
TESSERACT_CONFIG = "--psm 4"


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
class Content:
    """A file's text in line order, and its words with their boxes (none for plain text)."""

    text: str
    words: tuple[Word, ...] = ()


def load_text(path: Path, *, ocr: bool = False) -> Content:
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
        return Content(text, () if values else _pdf_words(path))
    if not ocr:
        raise ExtractionError(
            "PDF has no usable text layer (probably a scan). Re-run with --ocr "
            "(requires `uv sync --extra ocr` plus the tesseract and poppler binaries)."
        )
    try:
        from pdf2image import convert_from_path
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ExtractionError("OCR needs the 'ocr' extra: uv sync --extra ocr") from e
    return _ocr_images(convert_from_path(str(path), dpi=_scan_dpi(reader)))


def _scan_dpi(reader) -> int:
    """The resolution the first page was scanned at, up to 300 dpi. Rendering a 200 dpi
    scan at 300 dpi resamples it, and tesseract then misreads more of it."""
    page = reader.pages[0]
    images = [
        x.get_object()
        for x in (page["/Resources"].get("/XObject") or {}).values()
        if x.get_object().get("/Subtype") == "/Image"
    ]
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
    """OCR each page once: its words with their boxes, and its text in tesseract's line order."""
    try:
        import pytesseract
    except ImportError as e:  # pragma: no cover
        raise ExtractionError("OCR needs the 'ocr' extra: uv sync --extra ocr") from e
    words: list[Word] = []
    pages: list[str] = []
    for page_no, img in enumerate(images):
        data = pytesseract.image_to_data(
            img, config=TESSERACT_CONFIG, output_type=pytesseract.Output.DICT
        )
        lines: dict[tuple[int, int, int], list[str]] = {}
        for i, text in enumerate(data["text"]):
            if not text.strip():
                continue
            x, y = data["left"][i], data["top"][i]
            words.append(Word(text, x, y, x + data["width"][i], y + data["height"][i], page_no))
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(text)
        pages.append("\n".join(" ".join(line) for line in lines.values()))
    return Content("\n".join(pages), tuple(words))
