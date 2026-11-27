"""What reading a document costs, and the two limits that hold it down.

`--max-pages` refuses a document longer than the limit before any page is read, because
pages are what an OCR translation costs in memory and in time: a hosted deploy sets one,
so a visitor with a ten-page scan is told so rather than waiting out the server's
timeout. `OMP_THREAD_LIMIT` is the other half, one OCR thread per process. Both are
measured and sized in `docs/deploy.md`.
"""

import contextlib
import os
from pathlib import Path

import pytest
import synthetic_dd214 as form
from pypdf import PdfReader, PdfWriter

from dd214kw.cli import main
from dd214kw.extract import OCR_THREADS, ExtractionError, _ocr_images, page_count
from dd214kw.index import DEFAULT_INDEX

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def three_page_pdf(tmp_path: Path) -> Path:
    """One synthetic DD-214, bound three times into one file. Every value in it is made up."""
    one = PdfReader(form.write_text_pdf(tmp_path / "one.pdf"))
    writer = PdfWriter()
    for _ in range(3):
        writer.add_page(one.pages[0])
    out = tmp_path / "three-pages.pdf"
    with out.open("wb") as handle:
        writer.write(handle)
    return out


def test_pages_are_counted_without_reading_the_document(three_page_pdf):
    assert page_count(three_page_pdf) == 3
    assert page_count(FIX / "army_2000.txt") == 1


def test_a_document_past_the_limit_is_refused_and_says_by_how_much(
    three_page_pdf, monkeypatch, capsys
):
    # From the file's own directory, as the web server runs it, so the message is one line.
    monkeypatch.chdir(three_page_pdf.parent)

    code = main(["translate", three_page_pdf.name, "--max-pages", "2"])

    assert code == 2
    assert f"{three_page_pdf.name}: too many pages: 3 (limit 2)" in capsys.readouterr().err


def test_a_page_limit_of_zero_is_refused_rather_than_read_as_no_limit():
    with pytest.raises(SystemExit) as exit:
        main(["translate", "whatever.pdf", "--max-pages", "0"])

    assert exit.value.code == 2


@pytest.mark.parametrize("asked", [None, "4"])
def test_ocr_runs_on_one_thread_unless_the_caller_asked_for_more(asked, monkeypatch):
    monkeypatch.delenv("OMP_THREAD_LIMIT", raising=False)
    if asked:
        monkeypatch.setenv("OMP_THREAD_LIMIT", asked)

    # No pages, so this stops as soon as the limit is set, whether tesseract is here or not.
    with contextlib.suppress(ExtractionError):
        _ocr_images([])

    assert os.environ["OMP_THREAD_LIMIT"] == (asked or OCR_THREADS)


@pytest.mark.skipif(not DEFAULT_INDEX.exists(), reason="index not built")
def test_a_document_at_the_limit_is_translated(three_page_pdf, tmp_path):
    out = tmp_path / "report.md"
    argv = ["translate", str(three_page_pdf), "--max-pages", "3", "-f", "md", "-o", str(out)]

    assert main(argv) == 0
    assert "Civilian Workforce Keywords" in out.read_text(encoding="utf-8")
