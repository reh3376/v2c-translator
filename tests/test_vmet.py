"""VMET (DD Form 2586): its occupations, O*NET links and courses, alone and with a DD-214."""

import json
from datetime import date
from pathlib import Path

import pytest

from dd214kw.cli import main
from dd214kw.extractors import detect, read
from dd214kw.extractors.dd214 import Dd214, Dd214Json
from dd214kw.extractors.dd215 import Dd215Json
from dd214kw.extractors.vmet import Vmet
from dd214kw.index import DEFAULT_INDEX
from dd214kw.resolve import Profile, resolve

FIX = Path(__file__).parent / "fixtures"
VMET = FIX / "army_vmet.txt"  # the soldier of army_2000.txt; 92Y's list breaks across a page
ARMY = FIX / "army_2000.txt"
needs_index = pytest.mark.skipif(not DEFAULT_INDEX.exists(), reason="index not built")


def _resolve(*paths: Path) -> Profile:
    return resolve([f for p in paths for f in read(p)[1]])


def _translate_json(capsys, *paths: Path) -> dict:
    assert main(["translate", *map(str, paths), "-f", "json"]) == 0
    return json.loads(capsys.readouterr().out)


def _matches(report: dict) -> dict[str, dict]:
    codes = [m["code"] for m in report["matches"]]
    assert len(codes) == len(set(codes)), codes  # one match per code
    return {m["code"]: m for m in report["matches"]}


def test_detect_picks_each_fixture_s_extractor():
    expected = {
        "army_vmet.txt": Vmet,
        "army_2000.txt": Dd214,
        "navy_2022.txt": Dd214,
        "airforce.json": Dd214Json,
        "marines.json": Dd214Json,
        "army_2000_dd215.json": Dd215Json,
    }
    for name, extractor in expected.items():
        assert isinstance(detect((FIX / name).read_text()), extractor), name


def test_vmet_header_gives_the_service_context_and_layout():
    doc, _ = read(VMET)
    assert (doc.doc_type, doc.layout, doc.notes) == ("vmet", "2010", ())
    ctx = _resolve(VMET).context
    assert (ctx.branch, ctx.component, ctx.pay_grade, ctx.rank) == ("Army", "Active", "E6", None)
    assert ctx.as_of == date(2022, 3, 1)  # block 5, date of information


def test_entries_for_one_code_sum_their_months():
    by_code = {o.value.code: o.value for o in _resolve(VMET).occupations}
    assert by_code.keys() == {"92Y", "11B"}
    # 11B: JUN 2017 - MAY 2020 counts both months (36), and the earlier entry states 31.
    assert by_code["11B"].months == 36 + 31
    assert (by_code["11B"].start, by_code["11B"].end) == (date(2014, 10, 1), date(2020, 5, 1))
    assert by_code["92Y"].months == 22  # JUN 2020 - MAR 2022


def test_an_entry_split_by_a_page_break_keeps_all_its_onet_links():
    links = {
        (c.value.onet, c.value.title)
        for c in _resolve(VMET).civilian_equivalents
        if c.value.for_code == "92Y"
    }
    assert links == {  # DOT, OES and "OTHER RELATED" lines are not links
        ("53-7065.00", "Stockers and Order Fillers"),
        ("43-5071.00", "Shipping, Receiving, and Inventory Clerks"),
        ("43-5061.00", "Production, Planning, and Expediting Clerks"),
        ("11-3071.00", "Transportation, Storage, and Distribution Managers"),
    }


def test_courses_read_length_completion_and_description():
    training = {t.value.title: t.value for t in _resolve(VMET).training}
    assert {t: (c.weeks, c.completed) for t, c in training.items()} == {
        "UNIT SUPPLY SPECIALIST COURSE": (9, date(2020, 8, 1)),
        "ADVANCED LEADER COURSE": (6 + 3 / 7, date(2019, 3, 1)),
        "BASIC LEADER COURSE": (4, date(2017, 4, 1)),
        "COMBAT LIFESAVER COURSE - IET": (None, date(2014, 11, 1)),  # LENGTH: Unknown.
    }
    assert training["COMBAT LIFESAVER COURSE - IET"].description == (
        "Trains non-medical soldiers to provide enhanced first aid: hemorrhage control, "
        "airway management and casualty evacuation."
    )


def test_a_dd214_course_takes_the_vmet_s_ace_id_and_description():
    supply = next(
        t for t in _resolve(ARMY, VMET).training if t.value.title.startswith("UNIT SUPPLY")
    )
    assert supply.value.ace_id == "AR-1405-0921"
    assert supply.value.description.startswith("Upon completion of the course")
    assert [s.doc_type for s in supply.sources] == ["dd214", "vmet"]


def test_a_vmet_with_no_experience_entries_says_so(tmp_path):
    text = VMET.read_text()
    path = tmp_path / "vmet.txt"
    path.write_text(text[: text.index("1. OCCUPATION")] + text[text.index("TRAINING HISTORY:") :])
    doc, facts = read(path)
    assert len(doc.notes) == 1
    assert not resolve(facts).occupations


# --------------------------------------------------------------------------- reports


@needs_index
def test_a_vmet_alone_translates_with_its_own_onet_links(capsys):
    report = _translate_json(capsys, VMET)
    matches = _matches(report)

    assert matches.keys() == {"11B", "92Y"}
    assert matches["11B"]["specialty"]["months"] == 36 + 31  # both 11B entries
    # 43-5061.00 is on the VMET's 92Y list and not in the crosswalk for 92Y.
    clerks = next(o for o in matches["92Y"]["occupations"] if o["onet"] == "43-5061.00")
    assert "vmet" in clerks["sources"]
    assert not any(w.startswith("Could not match") for w in report["warnings"])


@needs_index
def test_a_specialty_on_a_dd214_and_a_vmet_is_one_match(capsys):
    report = _translate_json(capsys, ARMY, VMET)
    matches = _matches(report)

    assert matches.keys() == {"11B", "92Y"}
    assert matches["11B"]["specialty"]["months"] == max(76, 36 + 31)  # DD-214: 6 YRS 4 MOS
    assert matches["92Y"]["specialty"]["months"] == max(20, 22)  # VMET: JUN 2020 - MAR 2022
    assert [d["doc_type"] for d in report["documents"]] == ["dd214", "vmet"]
    # The DD-214's separation date (2022-06-01) is later than the VMET's date of information.
    context = report["profile"]["context"]
    assert (context["pay_grade"], context["rank"]) == ("E6", "SSG")
