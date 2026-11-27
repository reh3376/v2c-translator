"""Can the OCR tools run on this machine? A readiness check, not a translation.

Both tools write a temporary file before they do any work: pdf2image hands a page to
pdftoppm, pytesseract writes the image out and runs tesseract on it. So the temp
directory, not the document, is what decides whether a scanned page can be read at all,
and the hosted container is exactly where that goes wrong: its root filesystem is
read-only and its one writable path is the tmpfs the uploads go to, so Python's
`/tmp`, `/var/tmp` and `/usr/tmp` are all read-only and `TMPDIR` is the whole of it.

A container in that state still serves a healthy page and still translates a text PDF.
Only scans fail, and they fail per block 12 cell, which reads to a veteran as "your
document could not be read". `/api/readyz` runs this check instead, so a broken temp
directory is a container that never takes traffic.

Nothing here reads anybody's document: the page is drawn blank, in memory.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .extract import ExtractionError, OcrToolError, load_text

# A blank page, in pixels. Big enough for poppler and tesseract to treat it as a page,
# small enough that the whole check costs a fraction of a second.
PAGE = (240, 80)
# The tools being absent is not the tools being broken: a developer's machine runs without
# them and says so on the report instead, and `local` mode is still ready.
ABSENT = ("TesseractNotFoundError", "PopplerNotInstalledError", "PDFInfoNotInstalledError")
NOT_INSTALLED = "the OCR tools are not installed here, so scanned pages are not read"


def check() -> str:
    """What happened, for a human and for a log: `ok: ...`, or why the tools are absent.

    Raises OcrToolError when the tools are installed and could not run. That is the answer
    this exists for, and the caller turns it into a container that is not ready.
    """
    try:
        from PIL import Image
    except ImportError:
        return NOT_INSTALLED
    try:
        # A real temp directory, a real render, a real OCR pass, in whatever temp
        # directory this process has. The failure being checked for is raised by all three.
        with tempfile.TemporaryDirectory(prefix="dd214kw-ocr-check-") as work:
            page = Path(work) / "page.pdf"
            Image.new("L", PAGE, 255).save(page, "PDF", resolution=72.0)
            load_text(page, ocr=True)
    except OcrToolError as e:
        if e.kind in ABSENT:
            return NOT_INSTALLED
        raise
    except ExtractionError:  # the 'ocr' extra is not installed
        return NOT_INSTALLED
    except OSError as e:  # no writable temp directory at all, no permission, no space
        raise OcrToolError(e) from None
    return "ok: rendered a test page and read it"
