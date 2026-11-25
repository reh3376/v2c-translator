"""Several documents for one person: separate periods sum, DD-215 corrections replace."""

import json
import re
from pathlib import Path

import pytest

from dd214kw.cli import main
from dd214kw.extract import ExtractionError
from dd214kw.extractors import read
from dd214kw.index import DEFAULT_INDEX
from dd214kw.models import Duration
from dd214kw.resolve import Profile, resolve

FIX = Path(__file__).parent / "fixtures"
ARMY = FIX / "army_2000.txt"
ARMY_DD215 = FIX / "army_2000_dd215.json"  # corrects ARMY's period: net active 9y 1m, not 8y
DD215 = {"form": "DD-215", "corrects_separation_date": "2022-06-01"}  # same period, as JSON
needs_index = pytest.mark.skipif(not DEFAULT_INDEX.exists(), reason="index not built")


def _write_json(tmp_path: Path, name: str, obj: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(obj))
    return path


def _resolve(*paths: Path) -> Profile:
    return resolve([f for p in paths for f in read(p)[1]])


def _translate_json(capsys, *paths: Path) -> dict:
    assert main(["translate", *map(str, paths), "-f", "json"]) == 0
    return json.loads(capsys.readouterr().out)


def _experience(report: dict) -> list[str]:
    return [k["term"] for k in report["keywords"]["experience"]]


def _md_section(md: str, heading: str) -> list[str]:
    lines = md.splitlines()
    return lines[lines.index(f"## {heading}") + 2].split(", ")


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


def test_dd214_json_separation_dates_keep_periods_apart(tmp_path):
    first = {"branch": "NAVY", "pay_grade": "E-4", "net_active": "0004 00 00"}
    second = {"branch": "NAVY", "pay_grade": "E-6", "net_active": "0005 06 00"}
    profile = _resolve(
        _write_json(tmp_path, "first.json", first | {"separation_date": "2012-05-31"}),
        _write_json(tmp_path, "second.json", second | {"separation_date": "20180930"}),
    )
    assert profile.service_time["net_active"] == Duration(9, 6, 0)
    assert profile.context.pay_grade == "E6"  # the later separation is the current context


def test_a_bad_separation_date_is_an_extraction_error(tmp_path):
    path = _write_json(tmp_path, "dd214.json", {"branch": "NAVY", "separation_date": "last May"})
    with pytest.raises(ExtractionError):
        read(path)


# --------------------------------------------------------------------------- DD-215


@needs_index
def test_a_dd215_corrects_its_dd214_in_one_report(capsys):
    assert main(["translate", str(ARMY), str(ARMY_DD215), "-f", "md"]) == 0
    md = capsys.readouterr().out

    experience = _md_section(md, "Experience")
    assert "9+ Years Professional Experience" in experience
    assert "8+ Years Professional Experience" not in experience  # the uncorrected DD-214
    assert "17+ Years Professional Experience" not in experience  # added, not replaced
    assert "Fitness Program Design" in _md_section(md, "Transferable Skills")  # added course
    assert "- DD-214 layout: 2000" in md.splitlines()
    assert "- DD-215 layout: json" in md.splitlines()
    assert "| DD-214 / DD-215 entry | Matched code | Civilian occupations |" in md.splitlines()


def test_a_later_dd215_beats_an_earlier_one_for_the_same_period(tmp_path):
    earlier = _write_json(
        tmp_path, "earlier.json", DD215 | {"issued": "2023-03-15", "net_active": "0008 06 00"}
    )
    later = _write_json(
        tmp_path, "later.json", DD215 | {"issued": "20240110", "net_active": "0009 01 00"}
    )
    for paths in ((ARMY, earlier, later), (ARMY, later, earlier)):
        assert _resolve(*paths).service_time["net_active"] == Duration(9, 1, 0)


def test_a_dd215_without_corrects_separation_date_exits_2_naming_it(tmp_path, capsys):
    dd215 = _write_json(tmp_path, "undated_dd215.json", {"form": "DD-215", "net_active": "0009"})
    assert main(["translate", str(ARMY), str(dd215)]) == 2
    err = capsys.readouterr().err.replace("\n", "")
    assert "undated_dd215.json" in err
    assert "corrects_separation_date" in err


def test_a_dd215_corrects_a_dd214_json_with_the_same_separation_date(tmp_path):
    dd214 = {"form": "DD-214", "branch": "ARMY", "net_active": "0008 00 00"}
    path = _write_json(tmp_path, "dd214.json", dd214 | {"separation_date": "2022-06-01"})
    assert _resolve(path, ARMY_DD215).service_time["net_active"] == Duration(9, 1, 0)


def test_dd215_service_context_keys_are_ignored_with_one_note(tmp_path):
    context = {"branch": "ARMY", "component": "RA", "grade": "SFC", "pay_grade": "E-7"}
    doc, facts = read(_write_json(tmp_path, "dd215.json", DD215 | context))

    (note,) = doc.notes
    assert all(re.search(rf"\b{key}\b", note) for key in context)
    profile = resolve([*read(ARMY)[1], *facts])
    assert (profile.context.pay_grade, profile.context.rank) == ("E6", "SSG")  # DD-214's stand
