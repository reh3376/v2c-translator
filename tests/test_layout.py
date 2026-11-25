"""A DD-214 PDF read by where its blocks sit on the page.

The PDFs are fictional AUG 2009 forms that `synthetic_dd214.py` draws at test time, with
text in row-major order across the page so blocks 11/12 and 13/14 interleave the way a
scanned form's OCR layer does. Expected values come from what the generator draws.
"""

from pathlib import Path

import pytest
import synthetic_dd214 as form

from dd214kw.evidence import SourceFactory
from dd214kw.extract import load_text
from dd214kw.extractors import Dd214
from dd214kw.resolve import resolve


@pytest.fixture(scope="module")
def pdfs(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("dd214")


@pytest.fixture(scope="module")
def noisy_pdf(pdfs):
    return form.write_text_pdf(pdfs / "noisy.pdf", noisy=True)


def _line_order(pdf: Path):
    """The PDF read the way main read it: its text in line order, without word positions."""
    return Dd214().extract(load_text(pdf), SourceFactory.for_bytes(pdf.read_bytes()))


def _occupations(profile):
    return [(o.value.title, o.value.months) for o in profile.occupations]


def test_line_order_mixes_side_by_side_blocks(noisy_pdf):
    """The reported failure: read line by line, blocks that sit side by side mix."""
    _, facts = _line_order(noisy_pdf)
    before = resolve(facts)
    assert before.context.branch is None
    assert "net_active" not in before.service_time
    assert any("DATE ENTERED AD THIS PERIOD" in title for title, _ in _occupations(before))
    assert before.training == ()
