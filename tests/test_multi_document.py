"""Several documents for one person: separate periods sum, DD-215 corrections replace."""

import json
from pathlib import Path

import pytest

from dd214kw.cli import main
from dd214kw.index import DEFAULT_INDEX

FIX = Path(__file__).parent / "fixtures"
ARMY = FIX / "army_2000.txt"
needs_index = pytest.mark.skipif(not DEFAULT_INDEX.exists(), reason="index not built")


def _translate_json(capsys, *paths: Path) -> dict:
    assert main(["translate", *map(str, paths), "-f", "json"]) == 0
    return json.loads(capsys.readouterr().out)


def _experience(report: dict) -> list[str]:
    return [k["term"] for k in report["keywords"]["experience"]]


@needs_index
def test_two_dd214s_for_separate_periods_merge_into_one_report(tmp_path, capsys):
    earlier = tmp_path / "army_2014.txt"
    earlier.write_text(
        ARMY.read_text()
        .replace("2022 06 01", "2014 05 30")
        .replace("NET ACTIVE SERVICE THIS PERIOD 0008", "NET ACTIVE SERVICE THIS PERIOD 0003")
    )
    report = _translate_json(capsys, ARMY, earlier)

    assert [m["code"] for m in report["matches"]].count("11B") == 1
    assert len(report["documents"]) == 2
    assert report["profile"]["service_time"]["net_active"] == {"years": 11, "months": 0, "days": 0}
    assert "11+ Years Professional Experience" in _experience(report)


def test_a_file_that_fails_extraction_exits_2_naming_it(tmp_path, capsys):
    bad = tmp_path / "unrecognised.txt"
    bad.write_text("hello world")
    assert main(["translate", str(ARMY), str(bad)]) == 2
    assert "unrecognised.txt" in capsys.readouterr().err.replace("\n", "")
