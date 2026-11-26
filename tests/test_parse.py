import json
from dataclasses import asdict
from pathlib import Path

from dd214kw.evidence import OccupationHeld, Source
from dd214kw.extractors import read
from dd214kw.parse import (
    detect_version,
    parse_courses,
    parse_decorations,
    parse_duration,
    parse_specialties,
)
from dd214kw.resolve import resolve
from dd214kw.rules import rule_keywords, smart_title

FIX = Path(__file__).parent / "fixtures"
SOURCE = Source("dd214", "a" * 12, "block 11", None, 1.0)


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


# What a scanner's text layer left in blocks 11, 13 and 14 of a real AUG 2009 form: the
# "//" between entries read as "I I", a letter lost to the replacement character, a line
# wrapped between an entry's years and its months, and "NOTHING FOLLOWS" misread. The
# award and course text is the scan's; the specialty codes, titles and times are invented.
OCR_SPECIALTIES = (
    "25U60 2B SI GI NT SGT/ CHIEF - 11 YRS\n"
    "2 �OS I I 25B4L NETWORK SYSTEMS OPERATOR - 23 YRS 5 MOS I I NOTHTNG FOLLOWS"
)
OCR_AWARDS = (
    "JOL T MERLTORLOUS UNIT AWARD B 3RD AWARD) I I ARMY GOOD CONDUCT\n"
    "CONT IN BL CK 18\nNOTHTNG FOLLOWS"
)
OCR_COURSES = "ADV NCO CR, TANCOC � 2004\nAIRBORNE, I I SOCC J NTRUCTOR T AL NI NG CRS 2015"


def test_a_specialty_wrapped_between_its_years_and_months_keeps_both():
    """The entries are separated by "//", which OCR read as "I I", so the line break inside
    the first entry is only a wrap: "11 YRS" and "2 MOS" are one time in specialty, and the
    second entry's title starts at its code."""
    specs = parse_specialties(OCR_SPECIALTIES)
    assert [(s.raw, s.months) for s in specs] == [
        ("25U60 2B SI GI NT SGT/ CHIEF - 11 YRS 2 OS", 134),
        ("25B4L NETWORK SYSTEMS OPERATOR - 23 YRS 5 MOS", 281),
    ]


def test_a_misread_nothing_follows_is_not_an_entry():
    for entries in (
        parse_specialties(OCR_SPECIALTIES),
        parse_decorations(OCR_AWARDS),
        parse_courses(OCR_AWARDS),
    ):
        assert not any("NOTH" in str(entry) for entry in entries)


def test_a_continued_in_block_marker_is_not_an_award():
    assert not any("CONT IN" in d for d in parse_decorations(OCR_AWARDS))


def test_an_ocr_read_separator_splits_two_merged_entries():
    """ "//" read as "I I" merged two awards into one entry, and two courses into one."""
    assert len(parse_decorations(OCR_AWARDS)) == 2
    assert [c.raw for c in parse_courses(OCR_COURSES)] == [
        "ADV NCO CR, TANCOC 2004",
        "AIRBORNE",
        "SOCC J NTRUCTOR T AL NI NG CRS 2015",
    ]


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


def _specialties_only(*months: int):
    """A profile whose only facts are specialties: the record of service was not read."""
    return resolve(
        [
            OccupationHeld(None, f"25U{i}0 SIGNAL SUPPORT SPECIALIST", m, None, None, SOURCE)
            for i, m in enumerate(months, start=1)
        ]
    )


def test_service_length_is_the_longest_specialty_when_the_record_is_not_read():
    """Specialty periods overlap: one soldier's specialty changes as the career runs. Summed,
    a 12-year and a 23-year entry read as 35 years of service. The longest entry is the
    lower bound the documents support."""
    terms = {k.term for k in rule_keywords(_specialties_only(144, 281))}
    assert "23+ Years Professional Experience" in terms
    assert not any("35+" in t or "41+" in t for t in terms)


def test_service_length_says_it_is_a_lower_bound_from_one_specialty():
    kw = next(
        k
        for k in rule_keywords(_specialties_only(144, 281))
        if k.term.endswith("Years Professional Experience")
    )
    assert "lower bound" in kw.sources[0]


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
