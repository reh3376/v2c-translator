import json
from dataclasses import asdict
from pathlib import Path

from dd214kw.extractors import read
from dd214kw.parse import (
    detect_version,
    parse_courses,
    parse_duration,
    parse_specialties,
)
from dd214kw.resolve import resolve
from dd214kw.rules import rule_keywords, smart_title

FIX = Path(__file__).parent / "fixtures"


def test_army_2000_layout():
    doc, facts = read(FIX / "army_2000.txt")
    rec = resolve(facts)
    assert doc.layout == "2000"
    assert rec.context.branch == "Army"
    assert rec.context.pay_grade == "E6"
    assert [s.value.title.split()[0] for s in rec.occupations] == ["11B30", "92Y20"]
    assert [s.value.months for s in rec.occupations] == [76, 20]
    assert rec.service_time["net_active"].years == 8
    assert rec.service_time["foreign"].total_months == 14
    assert rec.service_time["sea"].is_zero
    assert len(rec.awards) == 13
    assert rec.awards[0].value.name.startswith("ARMY COMMENDATION MEDAL")
    assert [c.value.title for c in rec.training][:2] == [
        "BASIC LEADER COURSE",
        "ADVANCED LEADER COURSE",
    ]
    assert rec.training[1].value.weeks == 6 and rec.training[1].value.completed.year == 2019


def test_navy_2022_layout():
    doc, facts = read(FIX / "navy_2022.txt")
    rec = resolve(facts)
    assert doc.layout == "2022"
    assert rec.context.branch == "Navy"
    assert rec.context.component == "Regular"
    assert rec.context.pay_grade == "E6"
    assert [s.value.months for s in rec.occupations] == [102, 24]
    assert rec.service_time["sea"].years == 5
    assert len(rec.training) == 5
    awards = [(a.value.name, a.value.count) for a in rec.awards]
    assert ("SEA SERVICE DEPLOYMENT RIBBON", 3) in awards


def test_sensitive_blocks_never_captured():
    doc, facts = read(FIX / "army_2000.txt")
    rec = resolve(facts)
    blob = json.dumps([asdict(doc), *map(asdict, facts), asdict(rec)], default=str).upper()
    for s in ("000-00-0000", "19900101", "HONORABLE", "KBK", "123 TEST ST", "SAMPLE, JORDAN"):
        assert s not in blob


def test_version_detection():
    assert detect_version("CERTIFICATE OF UNIFORMED SERVICE ... DOD ID NUMBER") == "2022"
    assert detect_version("CERTIFICATE OF RELEASE OR DISCHARGE FROM ACTIVE DUTY") == "2000"
    assert detect_version("hello") == "unknown"


def test_durations():
    assert parse_duration("0004 02 13").total_months == 50
    assert parse_duration("3 YRS 6 MOS").total_months == 42
    assert parse_duration("1 YR").total_months == 12
    assert parse_duration("2015 06 01") is None  # a date, not a duration


def test_specialties_without_separators():
    specs = parse_specialties("0311 RIFLEMAN 3 YRS 0 MOS 3531 MOTOR VEHICLE OPERATOR 1 YR 6 MOS")
    assert [s.months for s in specs] == [36, 18]


def test_courses_units():
    c = parse_courses("FORKLIFT OPERATOR, 3 DAYS, JUN 2018//SAFETY OFFICER COURSE, 40 HRS, 2019")
    assert c[0].title == "FORKLIFT OPERATOR" and c[0].year == 2018
    assert c[1].weeks == 1.0


def test_json_input():
    rec = resolve(read(FIX / "airforce.json")[1])
    assert rec.context.branch == "Air Force" and rec.context.pay_grade == "E6"
    assert len(rec.occupations) == 2 and rec.service_time["net_active"].years == 9


def test_rule_keywords():
    rec = resolve(read(FIX / "army_2000.txt")[1])
    terms = {(k.category, k.term) for k in rule_keywords(rec)}
    assert ("leadership", "First-Line Supervision") in terms
    assert ("experience", "U.S. Army Veteran") in terms
    assert ("experience", "8+ Years Professional Experience") in terms
    assert ("skills", "First Aid") in terms
    perf = next(k for k in rule_keywords(rec) if k.term == "Recognized for Performance Excellence")
    assert "5 individual" in perf.sources[0]


def test_smart_title():
    assert smart_title("NCO ACADEMY") == "NCO Academy"
    assert smart_title("ARMY ACHIEVEMENT MEDAL (3RD AWARD)") == "Army Achievement Medal (3RD Award)"
    assert smart_title("ELECTRONICS TECHNICIAN A SCHOOL") == "Electronics Technician A School"


def test_ats_term_shortening():
    from dd214kw.models import _ats_term

    assert (
        _ats_term("HVAC-R Instructor (Heating, Ventilation, Air Conditioning, And Refrigeration)")
        == "HVAC-R Instructor"
    )
    assert _ats_term("Career/Technical Education Teachers, Postsecondary") == (
        "Career/Technical Education Teachers"
    )
    assert _ats_term("Over the Road Driver (OTR Driver)") == "Over the Road Driver (OTR Driver)"
