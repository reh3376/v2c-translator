import json
from pathlib import Path

from dd214kw.parse import (
    detect_version,
    parse_courses,
    parse_duration,
    parse_json,
    parse_specialties,
    parse_text,
)
from dd214kw.rules import rule_keywords, smart_title

FIX = Path(__file__).parent / "fixtures"


def test_army_2000_layout():
    rec = parse_text((FIX / "army_2000.txt").read_text())
    assert rec.form_version == "2000"
    assert rec.branch == "Army"
    assert rec.pay_grade == "E6"
    assert [s.raw.split()[0] for s in rec.specialties] == ["11B30", "92Y20"]
    assert [s.months for s in rec.specialties] == [76, 20]
    assert rec.net_active.years == 8
    assert rec.foreign_service.total_months == 14
    assert rec.sea_service.is_zero
    assert len(rec.decorations) == 13
    assert rec.decorations[0].startswith("ARMY COMMENDATION MEDAL")
    assert [c.title for c in rec.education][:2] == ["BASIC LEADER COURSE", "ADVANCED LEADER COURSE"]
    assert rec.education[1].weeks == 6 and rec.education[1].year == 2019


def test_navy_2022_layout():
    rec = parse_text((FIX / "navy_2022.txt").read_text())
    assert rec.form_version == "2022"
    assert rec.branch == "Navy"
    assert rec.component == "Regular"
    assert rec.pay_grade == "E6"
    assert [s.months for s in rec.specialties] == [102, 24]
    assert rec.sea_service.years == 5
    assert len(rec.education) == 5
    assert "SEA SERVICE DEPLOYMENT RIBBON (3)" in rec.decorations


def test_sensitive_blocks_never_captured():
    rec = parse_text((FIX / "army_2000.txt").read_text())
    blob = json.dumps(rec.to_dict()).upper()
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
    rec = parse_json(json.loads((FIX / "airforce.json").read_text()))
    assert rec.branch == "Air Force" and rec.pay_grade == "E6"
    assert len(rec.specialties) == 2 and rec.net_active.years == 9


def test_rule_keywords():
    rec = parse_text((FIX / "army_2000.txt").read_text())
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
