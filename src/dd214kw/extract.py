"""Get raw text out of a DD-214 file (text, PDF with a text layer, or scanned image/PDF)."""

from __future__ import annotations

import re
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


class ExtractionError(RuntimeError):
    pass


def load_text(path: Path, *, ocr: bool = False) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".text", ".md"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        return _pdf_text(path, ocr=ocr)
    if suffix in IMAGE_SUFFIXES:
        return _ocr_images([_open_image(path)])
    raise ExtractionError(f"Unsupported file type: {suffix} (use .pdf, .txt, or an image)")


def _pdf_text(path: Path, *, ocr: bool) -> str:
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
        return text
    if not ocr:
        raise ExtractionError(
            "PDF has no usable text layer (probably a scan). Re-run with --ocr "
            "(requires `uv sync --extra ocr` plus the tesseract and poppler binaries)."
        )
    try:
        from pdf2image import convert_from_path
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ExtractionError("OCR needs the 'ocr' extra: uv sync --extra ocr") from e
    return _ocr_images(convert_from_path(str(path), dpi=300))


def _open_image(path: Path):
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover
        raise ExtractionError("Image input needs the 'ocr' extra: uv sync --extra ocr") from e
    return Image.open(path)


def _ocr_images(images) -> str:
    try:
        import pytesseract
    except ImportError as e:  # pragma: no cover
        raise ExtractionError("OCR needs the 'ocr' extra: uv sync --extra ocr") from e
    return "\n".join(pytesseract.image_to_string(img, config="--psm 4") for img in images)
