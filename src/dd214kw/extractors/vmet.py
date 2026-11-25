"""VMET extractor: DD Form 2586, Verification of Military Experience and Training, as text.

The labels come from publicly posted samples of the 2010 edition. The line under the name
label also holds the member's name, so only the pay grade is read from it.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from ..evidence import (
    CivilianEquivalent,
    DocType,
    Document,
    Fact,
    OccupationHeld,
    ServiceContext,
    SourceFactory,
    TrainingCompleted,
)
from ..parse import detect_branch, normalize_pay_grade

MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
MONTH = rf"(?:{'|'.join(MONTHS)})\s+\d{{4}}"
RANGE = rf"(?P<start>{MONTH})(?:\s*-\s*(?P<end>{MONTH}))?"

TITLE_RE = re.compile(r"VERIFICATION\s+OF\s+MILITARY\s+EXPERIENCE\s+AND\s+TRAINING", re.I)
FORM_2010_RE = re.compile(r"DD\s+FORM\s+2586,\s*JAN\s+2010", re.I)
FURNITURE_RE = re.compile(
    rf"{TITLE_RE.pattern}(?:\s+PAGE\s+\d+\s+OF\s+\d+)?"
    r"|DD\s+FORM\s+2586,\s*\w+\s+\d{4}(?:\s+PREVIOUS\s+EDITION\s+IS\s+OBSOLETE\.?)?"
    r"|_{3,}",
    re.I,
)

PAY_GRADE_RE = re.compile(r"PAY\s+GRADE[^\n]*\n\s*[^\n]*?\b(?P<grade>[EWO]-\d{1,2})\b", re.I)
COMPONENT_RE = re.compile(  # "ARMY, GUARD 2015 JUL 01": block 4, then block 5
    rf"MILITARY\s+SERVICE\s+COMPONENT[^\n]*\n\s*(?P<block4>[^\n]*?)(?:\s+(?P<year>\d{{4}})\s+"
    rf"(?P<month>{'|'.join(MONTHS)})\s+(?P<day>\d{{1,2}}))?[^\S\n]*$",
    re.I | re.M,
)

# Each entry starts at one of these labels and runs to the next. "stop" chunks are skipped.
ENTRY_RE = re.compile(
    r"^[^\S\n]*(?:(?P<occupation>(?:\d+\.\s*)?OCCUPATION:)|(?P<course>MILITARY\s+TRAINING:)"
    r"|(?P<stop>TRAINING\s+HISTORY:|INFORMATION\s+NOT\s+AVAILABLE|END\s+OF\s+AUTOMATED))",
    re.I | re.M,
)

OCCUPATION_RE = re.compile(r"OCCUPATION:\s*(?P<code>[^,\n]+),\s*(?P<title>[^\n]+)", re.I)
EXPERIENCE_RANGE_RE = re.compile(
    rf"^[^\S\n]*{RANGE}(?:\s*\((?P<months>\d+)\s+MONTHS?\))?", re.I | re.M
)
RELATED_RE = re.compile(
    r"^[^\S\n]*RELATED\s+CIVILIAN\s+OCCUPATIONS?\s+FOR:\s*(?P<code>[A-Z0-9]+)[^\n]*"
    r"(?P<body>.*?)(?=^[^\S\n]*(?:OCCUPATION\s+DESCRIPTION|RELATED\s+CIVILIAN|OTHER\s+RELATED"
    r"|SPECIAL\s+QUALIFICATION|ADDITIONAL\s+QUALIFICATION)|\Z)",
    re.I | re.M | re.S,
)
ONET_RE = re.compile(r"(?P<title>[^()]+?)\s*\(ONET\s+(?P<onet>\d{2}-\d{4}\.\d{2})\)")

COURSE_RANGE_RE = re.compile(rf"MILITARY\s+TRAINING:\s*{RANGE}", re.I)
COURSE_RE = re.compile(
    r"^[^\S\n]*(?:ARMY|NAVY|AIR\s+FORCE|MARINE\s+CORPS|COAST\s+GUARD)\s+COURSE:\s*"
    r"(?P<code>[^,\n]+),\s*(?P<title>[^\n]+)",
    re.I | re.M,
)
LENGTH_RE = re.compile(
    r"LENGTH:\s*(?:(?P<weeks>\d+)\s+WEEKS?)?[\s,]*(?:(?P<days>\d+)\s+DAYS?)?", re.I
)
DESCRIPTION_RE = re.compile(r"COURSE\s+DESCRIPTION\s+FROM[^\n]*\n(?P<text>.*)", re.I | re.S)
HISTORY_COURSE_RE = re.compile(r"\([A-Z ]*TRAINING\s+HISTORY\s+COURSE:[^)]*\)", re.I)
ACE_ID_RE = re.compile(r"\b(?:AR|NV|AF|MC|CG)-\d{4}-\d{4}\b")


def _month(s: str) -> date:
    """The first day of a month written as "SEP 2014"."""
    mon, year = s.upper().split()
    return date(int(year), MONTHS.index(mon) + 1, 1)


def _links(chunk: str, source: SourceFactory) -> list[CivilianEquivalent]:
    """The O*NET lines under each "RELATED CIVILIAN OCCUPATIONS FOR: <code>" in an entry."""
    return [
        CivilianEquivalent(
            m["onet"],
            " ".join(m["title"].split()),
            r["code"].upper(),
            source("vmet", f"experience: {r['code'].upper()}"),
        )
        for r in RELATED_RE.finditer(chunk)
        for m in ONET_RE.finditer(r["body"])
    ]


def _held(chunk: str, source: SourceFactory) -> OccupationHeld | None:
    """The occupation an experience entry names, with its dates and months."""
    if not (head := OCCUPATION_RE.search(chunk)):
        return None
    code = head["code"].strip().upper()
    start = end = months = None
    if r := EXPERIENCE_RANGE_RE.search(chunk):
        start = _month(r["start"])
        end = _month(r["end"]) if r["end"] else None
        if r["months"]:
            months = int(r["months"])
        elif end:
            months = (end.year - start.year) * 12 + end.month - start.month + 1
    return OccupationHeld(
        code, head["title"].strip(), months, start, end, source("vmet", f"experience: {code}")
    )


def _merge_same_code(entries: list[OccupationHeld]) -> list[OccupationHeld]:
    """Entries for one code are separate stints in one job: sum months, span the dates."""
    groups: dict[str | None, list[OccupationHeld]] = {}
    for e in entries:
        groups.setdefault(e.code, []).append(e)
    merged = []
    for g in groups.values():
        months = [e.months for e in g if e.months is not None]
        starts = [e.start for e in g if e.start]
        ends = [e.end for e in g if e.end]
        merged.append(
            replace(
                g[0],
                months=sum(months) if months else None,
                start=min(starts, default=None),
                end=max(ends, default=None),
            )
        )
    return merged


def _course(chunk: str, source: SourceFactory) -> TrainingCompleted | None:
    if not (course := COURSE_RE.search(chunk)):
        return None
    completed = None
    if r := COURSE_RANGE_RE.search(chunk):
        completed = _month(r["end"] or r["start"])
    weeks = None
    if (length := LENGTH_RE.search(chunk)) and (length["weeks"] or length["days"]):
        weeks = int(length["weeks"] or 0) + int(length["days"] or 0) / 7
    description = None
    if d := DESCRIPTION_RE.search(chunk):
        description = " ".join(HISTORY_COURSE_RE.sub(" ", d["text"]).split()) or None
    ace_id = m.group(0) if (m := ACE_ID_RE.search(chunk)) else None
    code = course["code"].strip()
    return TrainingCompleted(
        course["title"].strip(),
        weeks,
        completed,
        ace_id,
        description,
        source("vmet", f"training: {code}"),
    )


class Vmet:
    """DD Form 2586 text: header blocks 2, 4 and 5, then the experience and training history."""

    doc_type: DocType = "vmet"

    def sniff(self, text: str) -> float:
        return 1.0 if TITLE_RE.search(text) else 0.0

    def extract(self, text: str, source: SourceFactory) -> tuple[Document, list[Fact]]:
        layout = "2010" if FORM_2010_RE.search(text) else "unknown"
        body = FURNITURE_RE.sub("", text)

        branch = component = as_of = None
        if c := COMPONENT_RE.search(body):
            branch = detect_branch(c["block4"])
            component = c["block4"].partition(",")[2].strip().title() or None
            if c["year"]:
                as_of = date(int(c["year"]), MONTHS.index(c["month"].upper()) + 1, int(c["day"]))
        grade = normalize_pay_grade(g["grade"]) if (g := PAY_GRADE_RE.search(body)) else None
        facts: list[Fact] = [
            ServiceContext(branch, component, grade, None, as_of, source(self.doc_type, "block 4"))
        ]

        held: list[OccupationHeld] = []
        hits = list(ENTRY_RE.finditer(body))
        for m, nxt in zip(hits, [*hits[1:], None], strict=True):
            chunk = body[m.start() : nxt.start() if nxt else len(body)]
            if m["occupation"]:
                facts += _links(chunk, source)
                held += [o] if (o := _held(chunk, source)) else []
            elif m["course"] and (course := _course(chunk, source)):
                facts.append(course)
        facts += _merge_same_code(held)

        notes = () if held else ("No occupation found in the experience history (block 6).",)
        return Document(self.doc_type, source.doc_id, layout, notes), facts
