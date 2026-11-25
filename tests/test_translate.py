"""End-to-end tests. Need a built index (dd214kw build-index --download); skipped otherwise."""

import json
from pathlib import Path

import pytest

from dd214kw.cli import main
from dd214kw.index import DEFAULT_INDEX, Index
from dd214kw.parse import parse_json, parse_text
from dd214kw.translate import translate

FIX = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.skipif(not DEFAULT_INDEX.exists(), reason="index not built")


@pytest.fixture(scope="module")
def index():
    return Index(DEFAULT_INDEX)


def _terms(report, cat):
    return [k.term for k in report.keywords[cat]]


def test_army_codes_and_military_only_soc(index):
    r = translate(index, parse_text((FIX / "army_2000.txt").read_text()))
    assert [(m.code, m.method) for m in r.matches] == [
        ("11B", "code-variant"),
        ("92Y", "code-variant"),
    ]
    onets = {o.onet for m in r.matches for o in m.occupations}
    assert not any(o.startswith("55-") for o in onets)  # military-only SOC never surfaces
    assert "53-7065.00" in onets  # 92Y -> Stockers and Order Fillers (DMDC)


def test_navy_title_and_parenthetical_rating(index):
    r = translate(index, parse_text((FIX / "navy_2022.txt").read_text()))
    assert [m.code for m in r.matches] == ["ET", "IT"]
    assert "Network and Computer Systems Administrators" in _terms(r, "job_titles") or any(
        "Network" in t for t in _terms(r, "job_titles")
    )
    assert "Maritime Operations" in _terms(r, "experience")


def test_airforce_obsolete_afsc(index):
    r = translate(index, parse_json(json.loads((FIX / "airforce.json").read_text())))
    m = r.matches[0]
    assert m.code == "3D172" and m.occupations  # retired 2023 AFSC still resolves


def test_marines(index):
    r = translate(index, parse_json(json.loads((FIX / "marines.json").read_text())))
    assert [m.code for m in r.matches] == ["0311", "3531"]
    assert any("Truck" in t or "Driver" in t for t in _terms(r, "job_titles"))


def test_ats_terms_are_short(index):
    r = translate(index, parse_text((FIX / "army_2000.txt").read_text()))
    ats = r.ats_keywords(40)
    assert 20 <= len(ats) <= 40
    assert all("," not in t and len(t.split()) <= 6 for t in ats)


def test_cli_json(capsys):
    assert main(["translate", str(FIX / "navy_2022.txt"), "-f", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["record"]["branch"] == "Navy" and out["ats_keywords"]


def test_pdf_text_layer(tmp_path):
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    pdf = tmp_path / "dd214.pdf"
    c = reportlab.Canvas(str(pdf))
    y = 800
    for line in (FIX / "army_2000.txt").read_text().splitlines():
        c.drawString(20, y, line[:110])
        y -= 12
        if y < 40:
            c.showPage()
            y = 800
    c.save()
    assert main(["translate", str(pdf), "-f", "ats"]) == 0
