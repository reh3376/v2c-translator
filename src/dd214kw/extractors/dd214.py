"""DD-214 extractors: the form's text (2000 and 2022 layouts) and pre-extracted JSON fields.

Both read the same document, so both emit `dd214` facts. The JSON form is that document's
fields already pulled out by another tool (e.g. an OCR/LLM pipeline).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from typing import Any

from ..evidence import (
    Award,
    DocType,
    Document,
    Fact,
    OccupationHeld,
    ServiceContext,
    ServiceTime,
    Source,
    SourceFactory,
    TrainingCompleted,
)
from ..models import Course, Duration, Specialty
from ..parse import (
    DURATION_STRICT_RE,
    detect_branch,
    detect_version,
    normalize_pay_grade,
    parse_courses,
    parse_decorations,
    parse_duration,
    parse_specialties,
    pay_grade_from_rank,
    segment,
)

# Fields that hold facts, and their block numbers for Source locators. The 2022 form
# renumbered most blocks; with an unknown layout, the locator is the field name.
FIELDS = ("branch", "specialty", "record", "decorations", "education")
BLOCKS: dict[str, dict[str, int]] = {
    "2000": {"branch": 2, "specialty": 11, "record": 12, "decorations": 13, "education": 14},
    "2022": {"branch": 2, "specialty": 12, "record": 13, "decorations": 14, "education": 15},
    "unknown": {"branch": 2},
}
# Service-time kind -> its line in the record of service.
RECORD_LINES: dict[str, str] = {
    "net_active": r"NET\s*ACTIVE\s*SERVICE",
    "prior_active": r"(?:TOTAL\s*)?PRIOR\s*ACTIVE\s*SERVICE",
    "foreign": r"FOREIGN\s*SERVICE",
    "sea": r"SEA\s*SERVICE",
}
COMPONENT_RE = re.compile(r"\b(REGULAR|RESERVE|NATIONAL\s*GUARD|ACTIVE)\b")
SEPARATION_DATE_RE = re.compile(
    r"SEPARATION\s*DATE\s*THIS\s*PERIOD\D{0,12}?(\d{4})\s*(\d{2})\s*(\d{2})"
)


def _record_subfield(record: str, label: str) -> Duration | None:
    m = re.search(label, record)
    return parse_duration(record[m.end() : m.end() + 120]) if m else None


def _separation_date(record: str) -> date | None:
    if m := SEPARATION_DATE_RE.search(record):
        try:
            return date(*(int(g) for g in m.groups()))
        except ValueError:
            pass
    return None


def _award_count(s: str) -> int:
    if m := re.search(r"\((\d+)\)|(\d+)(?:ST|ND|RD|TH)?\s*(?:AWARD|AWD|OLC|OAK)", s):
        return int(m.group(1) or m.group(2))
    return 1


# The award-count notation the form appends to a name: "(3)", "(2ND AWARD)", "W/ 1 OAK LEAF
# CLUSTER", "W/ 2 OLC". The count lives in Award.count, so the name is the award's identity.
AWARD_COUNT_SUFFIX_RE = re.compile(
    r"\s*\(\s*\d+(?:ST|ND|RD|TH)?(?:\s*(?:AWARD|AWD))?\s*\)\s*$"
    r"|\s*(?:W/|WITH)\s*\d+\s*(?:OAK\s*LEAF\s*CLUSTERS?|OLCS?)\s*$"
)


def _award_name(s: str) -> str:
    return AWARD_COUNT_SUFFIX_RE.sub("", s) or s


def _occupation_title(raw: str) -> str:
    """The entry without its time in specialty, which OccupationHeld.months carries."""
    return " ".join(DURATION_STRICT_RE.sub(" ", raw).split()).strip(" ,;-") or raw


def _facts(
    specialties: list[Specialty],
    courses: list[Course],
    decorations: list[str],
    service_time: Mapping[str, Duration | None],
    period_end: date | None,
    src: Mapping[str, Source],
) -> list[Fact]:
    """DD-214 fields -> facts. `src` gives the Source for each field and service-time kind."""
    facts: list[Fact] = [
        OccupationHeld(None, _occupation_title(s.raw), s.months, None, None, src["specialty"])
        for s in specialties
    ]
    facts += [
        TrainingCompleted(
            c.title, c.weeks, date(c.year, 1, 1) if c.year else None, None, None, src["education"]
        )
        for c in courses
    ]
    facts += [Award(_award_name(d), _award_count(d), src["decorations"]) for d in decorations]
    facts += [
        ServiceTime(kind, d, period_end, src[kind])
        for kind, d in service_time.items()
        if d is not None
    ]
    return facts


class Dd214:
    """DD-214 text, either layout. Fields are found by label text, not block number."""

    doc_type: DocType = "dd214"

    def sniff(self, text: str) -> float:
        if detect_version(text) != "unknown":
            return 1.0
        segs = segment(text)
        return 0.5 if any(k in segs for k in FIELDS) else 0.0

    def extract(self, text: str, source: SourceFactory) -> tuple[Document, list[Fact]]:
        segs = segment(text)
        layout = detect_version(text)
        blocks = BLOCKS[layout]
        src = {k: source(self.doc_type, f"block {blocks[k]}" if k in blocks else k) for k in FIELDS}
        src |= dict.fromkeys(RECORD_LINES, src["record"])

        branch_seg = segs.get("branch", "")
        branch = detect_branch(branch_seg) or detect_branch(segs["_head"] + " " + branch_seg)
        component = m.group(1).title() if (m := COMPONENT_RE.search(branch_seg)) else None
        grade = (segs.get("grade") or "").split("\n")[0].strip()[:40] or None
        pay_grade = (
            normalize_pay_grade(segs.get("pay_grade"))
            or pay_grade_from_rank(grade)
            or normalize_pay_grade(segs.get("grade"))
        )
        record = segs.get("record", "")
        period_end = _separation_date(record)
        specialties = parse_specialties(segs.get("specialty"))
        facts = [
            ServiceContext(branch, component, pay_grade, grade, period_end, src["branch"]),
            *_facts(
                specialties,
                parse_courses(segs.get("education")),
                parse_decorations(segs.get("decorations")),
                {kind: _record_subfield(record, rx) for kind, rx in RECORD_LINES.items()},
                period_end,
                src,
            ),
        ]

        notes = []
        if layout == "unknown":
            notes.append("Could not identify the DD-214 layout; results may be incomplete.")
        if not branch:
            notes.append("Branch of service not found (block 2).")
        if not specialties:
            notes.append("No specialty found (block 11 on 2000 form / block 12 on 2022 form).")
        return Document(self.doc_type, source.doc_id, layout, tuple(notes)), facts


# JSON key -> service-time kind.
JSON_TIME_KEYS: dict[str, str] = {
    "net_active": "net_active",
    "prior_active": "prior_active",
    "foreign_service": "foreign",
    "sea_service": "sea",
}
JSON_KEYS = {
    "branch",
    "component",
    "grade",
    "pay_grade",
    "specialty",
    "specialties",
    "decorations",
    "education",
    *JSON_TIME_KEYS,
}


def _as_text(v: str | Iterable[str] | None) -> str:
    if v is None:
        return ""
    return v if isinstance(v, str) else "//".join(v)


def _json_duration(v: object) -> Duration | None:
    if isinstance(v, dict):
        return Duration(int(v.get("years", 0)), int(v.get("months", 0)), int(v.get("days", 0)))
    return parse_duration(str(v)) if v else None


def _json_facts(
    data: Mapping[str, Any], source: Callable[[str], Source], period_end: date | None
) -> list[Fact]:
    """Facts from the JSON keys for specialties, education, decorations and service time.
    `source(key)` is the Source for the field under `key`."""
    spec_key = "specialty" if data.get("specialty") else "specialties"
    src = {k: source(k) for k in JSON_KEYS}
    src |= {"specialty": src[spec_key]}
    src |= {kind: src[key] for key, kind in JSON_TIME_KEYS.items()}
    return _facts(
        parse_specialties(_as_text(data.get(spec_key))),
        parse_courses(_as_text(data.get("education"))),
        parse_decorations(_as_text(data.get("decorations"))),
        {kind: _json_duration(data.get(key)) for key, kind in JSON_TIME_KEYS.items()},
        period_end,
        src,
    )


class Dd214Json:
    """Pre-extracted DD-214 fields as a JSON object.

    Keys: branch, component, grade, pay_grade, specialty, decorations, education,
    net_active, prior_active, foreign_service, sea_service. List or string values.
    """

    doc_type: DocType = "dd214"

    def sniff(self, text: str) -> float:
        try:
            data = json.loads(text)
        except ValueError:
            return 0.0
        return 1.0 if isinstance(data, dict) and JSON_KEYS & data.keys() else 0.0

    def extract(self, text: str, source: SourceFactory) -> tuple[Document, list[Fact]]:
        data = json.loads(text)
        raw_branch = data.get("branch")
        grade = data.get("grade")
        context = ServiceContext(
            detect_branch(raw_branch or "") or raw_branch,
            data.get("component"),
            normalize_pay_grade(data.get("pay_grade")) or pay_grade_from_rank(grade),
            grade,
            None,
            source(self.doc_type, "branch"),
        )
        facts = _json_facts(data, lambda key: source(self.doc_type, key), None)
        has_specialty = any(isinstance(f, OccupationHeld) for f in facts)
        notes = () if has_specialty else ("No specialty provided.",)
        return Document(self.doc_type, source.doc_id, "json", notes), [context, *facts]
