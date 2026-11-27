"""`dd214kw check-ocr`, which is what `/api/readyz` asks before a container takes traffic.

The failure it exists for cannot be reached by uploading anything: the hosted image runs
with a read-only root filesystem, and both OCR tools write a temporary file before they do
any work. A container whose temp directory is unwritable serves a healthy page, translates
a text PDF, and reads nothing at all off a scan.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile

import pytest
import synthetic_dd214 as form

from dd214kw.cli import main
from dd214kw.extract import OcrToolError
from dd214kw.ocr_check import NOT_INSTALLED, check

needs_tesseract = pytest.mark.skipif(
    not form.tools_available(), reason="needs the tesseract and pdftoppm binaries"
)
needs_ocr_extra = pytest.mark.skipif(
    not (importlib.util.find_spec("pytesseract") and importlib.util.find_spec("pdf2image")),
    reason="needs the 'ocr' extra: uv sync --extra ocr",
)


@needs_tesseract
@needs_ocr_extra
def test_a_machine_whose_ocr_tools_work_says_so():
    assert check().startswith("ok:")
    assert main(["check-ocr"]) == 0


@needs_tesseract
@needs_ocr_extra
def test_no_writable_temp_directory_is_not_ready(monkeypatch, tmp_path, capsys):
    """What the hosted container looks like when `TMPDIR` does not point at its tmpfs.
    Exit 3 and the error's class, so the route can log one line and say that this server
    could not read a scan, and `/api/readyz` can hold the container out of the rotation."""
    # tempfile caches the directory it chose, so the env variable is no use mid-process.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "read-only"))

    with pytest.raises(OcrToolError) as raised:
        check()
    assert raised.value.kind == "FileNotFoundError"

    assert main(["check-ocr"]) == 3
    assert "ocr-unavailable: FileNotFoundError" in capsys.readouterr().err


def test_a_machine_without_the_ocr_tools_is_still_ready(monkeypatch):
    """A developer's machine has no tesseract and is not a broken deploy. The report
    already says so per document; readiness is about what this machine promised."""
    monkeypatch.setitem(sys.modules, "PIL", None)

    assert check() == NOT_INSTALLED
    assert main(["check-ocr"]) == 0
