"""Resolution policy (docs/design/multi-document-input.md), from hand-made fact lists."""

from datetime import date

import pytest

from dd214kw.evidence import (
    Accomplishment,
    Award,
    CivilianEquivalent,
    Metric,
    OccupationHeld,
    ServiceContext,
    ServiceTime,
    SkillClaim,
    Source,
    TrainingCompleted,
)
from dd214kw.index import DEFAULT_INDEX, Index
from dd214kw.models import Duration
from dd214kw.resolve import resolve
from dd214kw.translate import translate


def src(doc_type="dd214", doc_id="aaaaaaaaaaaa", locator="block 2", issued=None):
    return Source(doc_type, doc_id, locator, issued, 1.0)


def ctx(branch, as_of=None, source=None, pay_grade="E5"):
    return ServiceContext(branch, None, pay_grade, None, as_of, source or src())


# --------------------------------------------------------------------------- ServiceTime

END = date(2020, 5, 31)
DD214_TIME = ServiceTime("net_active", Duration(4, 0, 0), END, src(locator="block 12"))
DD215_TIME = ServiceTime(
    "net_active",
    Duration(4, 2, 10),
    END,
    src("dd215", "bbbbbbbbbbbb", "block 12", date(2021, 1, 4)),
)


@pytest.mark.parametrize("facts", [[DD214_TIME, DD215_TIME], [DD215_TIME, DD214_TIME]])
def test_dd215_overrides_dd214_for_the_same_period(facts):
    assert resolve(facts).service_time == {"net_active": Duration(4, 2, 10)}


def test_later_dd215_overrides_earlier_one():
    later = ServiceTime(
        "net_active", Duration(4, 3, 0), END, src("dd215", "c", issued=date(2022, 1, 1))
    )
    assert resolve([DD214_TIME, later, DD215_TIME]).service_time["net_active"] == Duration(4, 3, 0)


def test_two_dd214s_for_separate_periods_sum():
    first, second = src(doc_id="a"), src(doc_id="b")
    profile = resolve(
        [
            ServiceTime("net_active", Duration(3, 8, 20), date(2012, 5, 31), first),
            ServiceTime("sea", Duration(1, 0, 0), date(2012, 5, 31), first),
            ServiceTime("net_active", Duration(4, 6, 15), date(2018, 9, 30), second),
            ServiceTime("sea", Duration(0, 0, 0), date(2018, 9, 30), second),
        ]
    )
    # 3y 8m 20d + 4y 6m 15d, carrying 30-day months and 12-month years
    assert profile.service_time == {"net_active": Duration(8, 3, 5), "sea": Duration(1, 0, 0)}


# --------------------------------------------------------------------------- ServiceContext


def test_most_recent_service_context_wins():
    old = ctx("Army", date(2015, 6, 1), src(doc_id="a"), pay_grade="E5")
    new = ctx("Army", date(2019, 6, 1), src(doc_id="b"), pay_grade="E6")
    assert resolve([new, old]).context is new
    assert resolve([old, new]).context is new
    assert resolve([old, new]).conflicts == ()  # a promotion is not a conflict


def test_service_context_recency_is_as_of_then_issued():
    undated = ctx("Navy", None, src(doc_id="a", issued=date(2024, 1, 1)))
    dated = ctx("Navy", date(2019, 1, 1), src(doc_id="b", issued=date(2019, 1, 1)))
    assert resolve([undated, dated]).context is dated
    early = ctx("Navy", None, src(doc_id="c", issued=date(2016, 1, 1)))
    assert resolve([undated, early]).context is undated


def test_branch_disagreement_yields_a_conflict():
    army = ctx("Army", date(2010, 1, 1), src(doc_id="a"))
    air_force = ctx("Air Force", date(2016, 1, 1), src(doc_id="b"))
    profile = resolve([army, air_force])
    assert profile.context is air_force
    (conflict,) = profile.conflicts
    assert conflict.field == "branch"
    assert conflict.values == ("Army", "Air Force")
    assert conflict.kept == "Air Force"
    assert conflict.sources == (army.source, air_force.source)
    assert conflict.message == "Documents disagree on branch (Army, Air Force); using Air Force."


def test_agreeing_or_missing_branches_are_not_conflicts():
    facts = [ctx("Navy", source=src(doc_id="a")), ctx(None, source=src(doc_id="b"))]
    assert resolve(facts).conflicts == ()


def test_no_facts_resolve_to_an_empty_profile():
    profile = resolve([])
    assert profile.context is None
    assert profile.occupations == profile.training == profile.awards == ()
    assert profile.service_time == {}
    assert profile.conflicts == ()


@pytest.mark.skipif(not DEFAULT_INDEX.exists(), reason="index not built")
def test_conflicts_surface_as_report_warnings():
    profile = resolve([ctx("Army", source=src(doc_id="a")), ctx("Navy", source=src(doc_id="b"))])
    assert translate(Index(DEFAULT_INDEX), profile).warnings == [profile.conflicts[0].message]


# --------------------------------------------------------------------------- OccupationHeld


def test_occupations_by_code_else_title_union_sources_and_keep_max_months():
    dd214, jst, vmet = src(doc_id="a"), src("jst", "b"), src("vmet", "c")
    profile = resolve(
        [
            OccupationHeld("11B", "Infantryman", 36, None, None, dd214),
            OccupationHeld(None, "Unit Supply Specialist", None, None, None, dd214),
            OccupationHeld("11b ", "INFANTRYMAN", 48, date(2014, 6, 2), None, jst),
            OccupationHeld(None, "unit supply  specialist.", 20, None, None, vmet),
        ]
    )
    assert [(o.value.title, o.value.months, o.sources) for o in profile.occupations] == [
        ("Infantryman", 48, (dd214, jst)),
        ("Unit Supply Specialist", 20, (dd214, vmet)),
    ]


# --------------------------------------------------------------------------- CivilianEquivalent


def test_civilian_equivalents_by_onet_union_sources():
    a, b = src("vmet", "a"), src("vmet", "b")
    profile = resolve(
        [
            CivilianEquivalent("53-7065.00", "Stockers and Order Fillers", a),
            CivilianEquivalent("11-3071.00", "Transportation Managers", a),
            CivilianEquivalent("53-7065.00", "Stock Clerks", b),
        ]
    )
    assert [(c.value.onet, c.sources) for c in profile.civilian_equivalents] == [
        ("53-7065.00", (a, b)),
        ("11-3071.00", (a,)),
    ]


# --------------------------------------------------------------------------- TrainingCompleted


def course(title, year, ace_id=None, description=None, source=None):
    return TrainingCompleted(title, 4.0, date(year, 1, 1), ace_id, description, source or src())


def test_same_course_from_two_sources_collapses_to_one_item_with_two_sources():
    dd214 = course("BASIC LEADER COURSE", 2017, source=src(locator="block 14"))
    jst = course(
        "Basic Leader Course", 2017, "AR-2201-0001", "Leadership fundamentals", src("jst", "b")
    )
    (item,) = resolve([dd214, jst]).training
    assert item.sources == (dd214.source, jst.source)
    assert item.value is jst  # prefer the fact with ace_id / description


def test_training_by_ace_id_prefers_the_described_fact():
    bare = course("BLC", 2017, "AR-2201-0001", source=src("jst", "a"))
    described = course("Basic Leader Course", 2016, "AR-2201-0001", "Leadership", src("jst", "b"))
    (item,) = resolve([bare, described]).training
    assert item.value is described and len(item.sources) == 2


def test_training_with_different_ace_ids_or_years_stays_separate():
    profile = resolve(
        [
            course("Basic Leader Course", 2017, "AR-2201-0001"),
            course("Basic Leader Course", 2017, "AR-2201-0002"),
            course("Combat Lifesaver Course", 2015),
            course("Combat Lifesaver Course", 2019),
        ]
    )
    assert len(profile.training) == 4


# --------------------------------------------------------------------------- Award


def test_awards_by_normalized_name_keep_max_count():
    a, b = src(doc_id="a"), src(doc_id="b")
    profile = resolve(
        [
            Award("Army Achievement Medal", 2, a),
            Award("Army Good Conduct Medal", 1, a),
            Award("ARMY ACHIEVEMENT MEDAL", 3, b),
        ]
    )
    assert [(r.value.count, r.sources) for r in profile.awards] == [(3, (a, b)), (1, (a,))]


# --------------------------------------------------------------------------- free text


def test_accomplishments_and_skill_claims_by_normalized_text_union_sources():
    epb, resume = src("eval", "a", "EPB bullet 3"), src("resume", "b", "Skills")
    profile = resolve(
        [
            Accomplishment("Supervised 12 Airmen.", (Metric("people", 12),), epb),
            Accomplishment("supervised 12 airmen", (), resume),
            SkillClaim("Python", "technology", resume),
            SkillClaim("Security+", "certification", resume),
            SkillClaim("python", "technology", epb),
        ]
    )
    assert [r.sources for r in profile.accomplishments] == [(epb, resume)]
    assert [(r.value.term, r.sources) for r in profile.skill_claims] == [
        ("Python", (resume, epb)),
        ("Security+", (resume,)),
    ]
