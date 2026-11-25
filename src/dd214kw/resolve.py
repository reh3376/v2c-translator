"""Merge facts from every document read into one Profile.

The only owner of deduplication and conflict policy. The policy is the table in
docs/design/multi-document-input.md ("Resolution policy"); each rule below names its row.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import date

from .evidence import (
    Accomplishment,
    Award,
    CivilianEquivalent,
    Fact,
    OccupationHeld,
    ServiceContext,
    ServiceTime,
    SkillClaim,
    Source,
    TrainingCompleted,
)
from .models import Duration


@dataclass(frozen=True, slots=True)
class Resolved[T]:
    value: T
    sources: tuple[Source, ...]  # every document that supports it


@dataclass(frozen=True, slots=True)
class Conflict:
    """Documents that disagree. Surfaced as a warning, never silently dropped."""

    field: str
    values: tuple[str, ...]  # every distinct value, in the order first seen
    kept: str  # the value the profile uses
    sources: tuple[Source, ...]

    @property
    def message(self) -> str:
        return f"Documents disagree on {self.field} ({', '.join(self.values)}); using {self.kept}."


@dataclass(frozen=True, slots=True)
class Profile:
    context: ServiceContext | None  # most recent as_of, then issued; None if no document says
    occupations: tuple[Resolved[OccupationHeld], ...]
    civilian_equivalents: tuple[Resolved[CivilianEquivalent], ...]
    training: tuple[Resolved[TrainingCompleted], ...]
    awards: tuple[Resolved[Award], ...]
    service_time: Mapping[str, Duration]  # summed across distinct periods
    accomplishments: tuple[Resolved[Accomplishment], ...]
    skill_claims: tuple[Resolved[SkillClaim], ...]
    conflicts: tuple[Conflict, ...]


def resolve(facts: Iterable[Fact]) -> Profile:
    facts = list(facts)

    def of[F](kind: type[F]) -> list[F]:
        return [f for f in facts if isinstance(f, kind)]

    context, conflicts = _context(of(ServiceContext))
    return Profile(
        context=context,
        occupations=_union(of(OccupationHeld), _occupation_key, _longest),
        civilian_equivalents=_union(of(CivilianEquivalent), lambda f: f.onet.strip()),
        training=_training(of(TrainingCompleted)),
        awards=_union(of(Award), lambda f: _norm(f.name), _most_awarded),
        service_time=_service_time(of(ServiceTime)),
        accomplishments=_union(of(Accomplishment), lambda f: _norm(f.text)),
        skill_claims=_union(of(SkillClaim), lambda f: _norm(f.term)),
        conflicts=conflicts,
    )


# --------------------------------------------------------------------------- helpers


def _norm(s: str) -> str:
    """Identity form of a title or name: case, punctuation and spacing don't count."""
    return " ".join(re.findall(r"[a-z0-9]+", s.casefold()))


def _union[F: Fact](
    facts: list[F],
    key: Callable[[F], Hashable],
    merge: Callable[[list[F]], F] = lambda group: group[0],
) -> tuple[Resolved[F], ...]:
    """Group facts by identity key (first-seen order) and union their sources."""
    groups: dict[Hashable, list[F]] = {}
    for f in facts:
        groups.setdefault(key(f), []).append(f)
    return tuple(_resolved(g, merge(g)) for g in groups.values())


def _resolved[F: Fact](group: list[F], value: F) -> Resolved[F]:
    return Resolved(value, tuple(dict.fromkeys(f.source for f in group)))


# ServiceContext: keep latest by as_of / issued; a branch disagreement is a Conflict.
def _context(facts: list[ServiceContext]) -> tuple[ServiceContext | None, tuple[Conflict, ...]]:
    if not facts:
        return None, ()
    latest = max(facts, key=lambda f: (f.as_of or date.min, f.source.issued or date.min))
    branched = [f for f in facts if f.branch]
    branches = tuple(dict.fromkeys(f.branch for f in branched))
    if len(branches) < 2:
        return latest, ()
    sources = tuple(dict.fromkeys(f.source for f in branched))
    return latest, (Conflict("branch", branches, latest.branch or "none", sources),)


# OccupationHeld: normalized code, else normalized title; union sources, months = max.
def _occupation_key(f: OccupationHeld) -> tuple[str, str]:
    return ("code", _norm(f.code)) if f.code else ("title", _norm(f.title))


def _longest(group: list[OccupationHeld]) -> OccupationHeld:
    months = [f.months for f in group if f.months is not None]
    return replace(group[0], months=max(months) if months else None)


# Award: normalized name; count = max.
def _most_awarded(group: list[Award]) -> Award:
    return replace(group[0], count=max(f.count for f in group))


# TrainingCompleted: ace_id, else (normalized title, year); prefer the fact with
# ace_id/description. A fact without an ace_id joins a course with the same title and
# year, so the DD-214's entry and the JST's entry for one course collapse. Two different
# ace_ids are two courses.
def _training(facts: list[TrainingCompleted]) -> tuple[Resolved[TrainingCompleted], ...]:
    groups: list[list[TrainingCompleted]] = []
    by_ace: dict[str, list[TrainingCompleted]] = {}
    by_title: dict[tuple[str, int | None], list[TrainingCompleted]] = {}
    for f in facts:
        title_key = (_norm(f.title), f.completed.year if f.completed else None)
        group = by_ace.get(f.ace_id) if f.ace_id else None
        if group is None and (g := by_title.get(title_key)) is not None:
            group_ace = next((x.ace_id for x in g if x.ace_id), None)
            if not (f.ace_id and group_ace):
                group = g
        if group is None:
            group = []
            groups.append(group)
        group.append(f)
        by_title.setdefault(title_key, group)
        if f.ace_id:
            by_ace.setdefault(f.ace_id, group)
    return tuple(_resolved(g, _best_documented(g)) for g in groups)


def _best_documented(group: list[TrainingCompleted]) -> TrainingCompleted:
    return max(group, key=lambda f: (f.ace_id is not None, f.description is not None))


# ServiceTime: (kind, period_end); DD-215 > DD-214 for the same period; sum across periods.
def _service_time(facts: list[ServiceTime]) -> dict[str, Duration]:
    per_period: dict[tuple[str, date | None], ServiceTime] = {}
    for f in facts:
        k = (f.kind, f.period_end)
        if k not in per_period or _precedence(f) > _precedence(per_period[k]):
            per_period[k] = f
    totals: dict[str, Duration] = {}
    for (kind, _), f in per_period.items():
        totals[kind] = _add(totals[kind], f.duration) if kind in totals else f.duration
    return totals


def _precedence(f: ServiceTime) -> tuple[bool, date]:
    """A DD-215 corrects the DD-214 for its period; a later correction beats an earlier one."""
    return (f.source.doc_type == "dd215", f.source.issued or date.min)


def _add(a: Duration, b: Duration) -> Duration:
    """Sum two service durations, carrying 30-day months and 12-month years."""
    days = a.days + b.days
    months = a.months + b.months + days // 30
    return Duration(a.years + b.years + months // 12, months % 12, days % 30)
