"""Facts and their provenance: the only place either is defined.

Extractors turn a document into facts of the eight kinds below; `resolve.py` merges them
into a Profile. No fact kind has a field for a name, ID number, date of birth, address,
characterization or separation code, and the two free-text kinds (`Accomplishment.text`,
`SkillClaim.term`) pass through `scrub()` whenever they are constructed. That makes this
module the single owner of the privacy guarantee, instead of every extractor.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

from .models import Duration

DocType = Literal["dd214", "dd215", "ngb22", "jst", "vmet", "eval", "resume", "facts-json"]

# How output names each document type. Readers use this instead of naming types themselves.
DOC_LABELS: dict[DocType, str] = {
    "dd214": "DD-214",
    "dd215": "DD-215",
    "ngb22": "NGB-22",
    "jst": "JST",
    "vmet": "VMET",
    "eval": "Evaluation",
    "resume": "Resume",
    "facts-json": "Facts JSON",
}


@dataclass(frozen=True, slots=True)
class Source:
    doc_type: DocType
    doc_id: str  # first 12 hex of sha256(file bytes); never a name or ID number
    locator: str  # "block 12", "JST: Military Experience", "EPB bullet 3"
    issued: date | None  # document date; drives recency in conflicts
    confidence: float  # 1.0 official structured field; <1.0 OCR / model-extracted


@dataclass(frozen=True, slots=True)
class SourceFactory:
    """Makes the Sources for one document. The caller binds the document's identity."""

    doc_id: str

    @classmethod
    def for_bytes(cls, data: bytes) -> SourceFactory:
        return cls(hashlib.sha256(data).hexdigest()[:12])

    def __call__(
        self,
        doc_type: DocType,
        locator: str,
        issued: date | None = None,
        confidence: float = 1.0,
    ) -> Source:
        return Source(doc_type, self.doc_id, locator, issued, confidence)


@dataclass(frozen=True, slots=True)
class Document:
    """One document read, as the report lists it. Notes are what extraction couldn't find."""

    doc_type: DocType
    doc_id: str
    layout: str  # the extractor's name for the layout it read: "2000", "2022", "json"
    notes: tuple[str, ...] = ()


# --------------------------------------------------------------------------- privacy

_PII_RE = re.compile(
    "|".join(
        (
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b\d{9,10}\b",  # SSN without dashes, DoD ID
            r"\b(?:19|20)\d{2}-?(?:0[1-9]|1[0-2])-?(?:0[1-9]|[12]\d|3[01])\b",  # YYYYMMDD
            r"\b\d{1,2}[/.-]\d{1,2}[/.-](?:19|20)?\d{2}\b",  # MM/DD/YYYY
            r"\b\d{1,2}\s*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?\s*"
            r"(?:19|20)\d{2}\b",  # 01 JAN 1990
            r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",  # email
            r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b",  # phone
            r"\b\d{1,6}(?-i:(?:\s+[A-Z][\w.]*){1,3})\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|BLVD|DR|"
            r"DRIVE|LN|LANE|CT|COURT|HWY|PKWY|CIR|PL)\b\.?",  # street address
            r"(?-i:\b[A-Z]{2})\s+\d{5}(?:-\d{4})?\b",  # state + ZIP
            r"\b(?:GENERAL\s*\(?\s*)?(?:UNDER\s+)?(?:OTHER\s+THAN\s+)?(?:DIS)?HONORABLE"
            r"(?:\s+CONDITIONS)?\)?|\bBAD\s+CONDUCT\b|\bUNCHARACTERIZED\b",  # characterization
            r"\b(?:SEPARATION|SPD|RE-?ENTRY)\s+CODE\s*[:#]?\s*[A-Z0-9-]{1,4}\b",  # coded reasons
            r"\bSPD\s*:?\s*[A-Z]{3}\b|\bRE-\d[A-Z]?\b",
        )
    ),
    re.IGNORECASE,
)


def scrub(text: str) -> str:
    """Redact ID numbers, dates, contact details, addresses, characterization of service
    and separation/reentry codes from free text. Idempotent."""
    return re.sub(r"\s+", " ", _PII_RE.sub("[redacted]", text)).strip()


# --------------------------------------------------------------------------- fact kinds


@dataclass(frozen=True, slots=True)
class ServiceContext:
    branch: str | None  # None when the document names no branch; see resolve()
    component: str | None
    pay_grade: str | None  # normalized: E5, W2, O3
    rank: str | None
    as_of: date | None
    source: Source


@dataclass(frozen=True, slots=True)
class OccupationHeld:
    code: str | None
    title: str  # as the document words it (a DD-214 entry includes its code and time)
    months: int | None
    start: date | None
    end: date | None
    source: Source


@dataclass(frozen=True, slots=True)
class CivilianEquivalent:
    onet: str
    title: str
    for_code: str | None  # the military code the document lists it under
    source: Source


@dataclass(frozen=True, slots=True)
class TrainingCompleted:
    title: str
    weeks: float | None
    completed: date | None  # January 1 when the document gives only the year
    ace_id: str | None
    description: str | None
    source: Source


@dataclass(frozen=True, slots=True)
class Award:
    name: str
    count: int
    source: Source


@dataclass(frozen=True, slots=True)
class ServiceTime:
    kind: Literal["net_active", "prior_active", "foreign", "sea"]
    duration: Duration
    period_end: date | None
    source: Source


@dataclass(frozen=True, slots=True)
class Metric:
    """A scope figure from an accomplishment ("supervised 12", "$4.2M", "38 vehicles")."""

    kind: Literal["people", "budget", "equipment"]
    value: float


@dataclass(frozen=True, slots=True)
class Accomplishment:
    text: str
    metrics: tuple[Metric, ...]
    source: Source

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", scrub(self.text))


@dataclass(frozen=True, slots=True)
class SkillClaim:
    term: str
    kind: Literal["skill", "technology", "certification", "clearance"]
    source: Source

    def __post_init__(self) -> None:
        object.__setattr__(self, "term", scrub(self.term))


Fact = (
    ServiceContext
    | OccupationHeld
    | CivilianEquivalent
    | TrainingCompleted
    | Award
    | ServiceTime
    | Accomplishment
    | SkillClaim
)
