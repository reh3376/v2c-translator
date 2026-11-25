"""Data models shared across parsing, translation and rendering."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


def _ats_term(term: str) -> str:
    """Shorten a keyword for a comma-separated ATS string.

    Drops long parenthetical expansions ("HVAC-R Instructor (Heating, Ventilation, ...)")
    and qualifiers after a top-level comma ("..., Postsecondary").
    """
    term = re.sub(r"\s*\(([^()]*)\)", lambda m: "" if len(m[1].split()) > 3 else m[0], term)
    return re.split(r",(?![^()]*\))", term)[0].strip()


@dataclass(slots=True)
class Duration:
    years: int = 0
    months: int = 0
    days: int = 0

    @property
    def total_months(self) -> int:
        return self.years * 12 + self.months

    @property
    def is_zero(self) -> bool:
        return self.years == 0 and self.months == 0 and self.days == 0


@dataclass(slots=True)
class Specialty:
    """One entry from block 11 (2000 form) / block 12 (2022 form)."""

    raw: str
    months: int | None = None


@dataclass(slots=True)
class Course:
    """One entry from block 14 (2000) / block 15 (2022)."""

    raw: str
    title: str
    weeks: float | None = None
    year: int | None = None


@dataclass(slots=True)
class ServiceRecord:
    """The occupation-relevant subset of a DD-214.

    PII and adverse-action fields (SSN/DoD ID, DOB, addresses, character of service,
    separation/reentry codes, narrative reason) are deliberately never captured.
    """

    form_version: str = "unknown"  # "2000", "2022", "json", "unknown"
    branch: str | None = None  # Army, Navy, Air Force, Marine Corps, Coast Guard, Space Force
    component: str | None = None
    grade: str | None = None
    pay_grade: str | None = None  # normalized: E5, W2, O3
    specialties: list[Specialty] = field(default_factory=list)
    decorations: list[str] = field(default_factory=list)
    education: list[Course] = field(default_factory=list)
    net_active: Duration | None = None
    prior_active: Duration | None = None
    foreign_service: Duration | None = None
    sea_service: Duration | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class OccupationLink:
    onet: str
    title: str
    weight: float
    sources: list[str]


@dataclass(slots=True)
class SpecialtyMatch:
    specialty: Specialty
    svc: str | None = None
    code: str | None = None
    title: str | None = None
    method: str | None = None  # "code", "code-variant", "title"
    occupations: list[OccupationLink] = field(default_factory=list)


@dataclass(slots=True)
class Keyword:
    term: str
    category: str
    score: float
    sources: list[str] = field(default_factory=list)


CATEGORIES: dict[str, str] = {
    "job_titles": "Civilian Job Titles",
    "skills": "Transferable Skills",
    "knowledge": "Knowledge Areas",
    "technologies": "Technologies & Tools",
    "work_activities": "Work Activities",
    "leadership": "Leadership & Management",
    "training": "Training & Certifications",
    "recognition": "Recognition",
    "experience": "Experience",
}


@dataclass(slots=True)
class KeywordReport:
    record: ServiceRecord
    matches: list[SpecialtyMatch]
    keywords: dict[str, list[Keyword]]
    warnings: list[str] = field(default_factory=list)

    def ats_keywords(self, limit: int = 40) -> list[str]:
        """Flat, de-duplicated list of short terms, round-robin across categories.

        Work activities are full sentences (resume bullet material), so they're excluded;
        qualifiers after a comma ("..., Postsecondary") and long phrases are dropped.
        """
        order = [
            "job_titles",
            "skills",
            "technologies",
            "leadership",
            "knowledge",
            "training",
            "experience",
            "recognition",
        ]
        seen: set[str] = set()
        out: list[str] = []
        per_cat = {c: iter(self.keywords.get(c, [])) for c in order}
        # Round-robin so one category can't crowd out the rest.
        while len(out) < limit and per_cat:
            for cat in list(per_cat):
                kw = next(per_cat[cat], None)
                if kw is None:
                    del per_cat[cat]
                    continue
                term = _ats_term(kw.term)
                key = term.casefold()
                if key not in seen and len(term.split()) <= 6:
                    seen.add(key)
                    out.append(term)
                if len(out) >= limit:
                    break
        return out

    def to_dict(self) -> dict:
        return {
            "record": self.record.to_dict(),
            "matches": [asdict(m) for m in self.matches],
            "keywords": {c: [asdict(k) for k in ks] for c, ks in self.keywords.items()},
            "ats_keywords": self.ats_keywords(),
            "warnings": self.warnings,
        }
