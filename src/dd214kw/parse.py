"""Field parsers for DD-214 text (2000 "Certificate of Release or Discharge" and 2022
"Certificate of Uniformed Service" layouts). The DD-214 extractor (extractors/dd214.py)
assembles their results into facts.

Segmentation is label-based rather than block-number-based, so the same code
handles both layouts (blocks were renumbered in 2022). Labels for PII and
adverse-action blocks are matched only so they can bound neighbouring segments;
their contents are discarded.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from rapidfuzz import fuzz

from .canonical import canonical_course
from .models import Course, Duration, Specialty

# (segment key, label regex). Order doesn't matter; segments are sorted by position.
LABELS: list[tuple[str, str]] = [
    ("name", r"NAME\s*\(\s*LAST"),
    ("branch", r"DEPARTMENT,?\s*COMPONENT,?\s*(?:AND|&)\s*BRANCH|BRANCH\s*(?:AND|&)\s*COMPONENT"),
    ("_id", r"SOCIAL\s*SECURITY\s*(?:NUMBER|NO)|DO[DW]\s*ID\s*(?:NUMBER|NO)"),
    ("grade", r"GRADE,?\s*RATE,?\s*OR\s*RANK"),
    ("pay_grade", r"(?<!OF )PAY\s*GRADE"),
    ("_dob", r"DATE\s*OF\s*BIRTH"),
    ("_reserve_obligation", r"RESERVE\s*OBLIGATION"),
    ("_reserve_status", r"RESERVE\s*STATUS"),
    ("_place_of_entry", r"PLACE\s*OF\s*ENTRY"),
    ("_home_of_record", r"HOME\s*OF\s*RECORD"),
    ("last_duty", r"LAST\s*DUTY\s*ASSIGNMENT"),
    ("_station_separated", r"STATION\s*WHERE\s*SEPARATED"),
    ("_command_transferred", r"COMMAND\s*TO\s*WHICH\s*TRANSFERRED"),
    ("_sgli", r"SGLI\s*COVERAGE"),
    ("specialty", r"(?:PRIMARY\s*)?SPECIALTY"),
    ("record", r"RECORD\s*OF\s*SERVICE"),
    (
        "decorations",
        r"DECORATIONS,?\s*MEDALS(?:,?\s*BADGES)?(?:,?\s*CITATIONS)?(?:,?\s*(?:AND\s*)?"
        r"CAMPAIGN\s*RIBBONS)?(?:\s*AWARDED\s*OR\s*AUTHORIZED)?",
    ),
    ("education", r"(?:MILITARY|UNIFORMED\s*SERVICE)\s*EDUCATION"),
    ("_veap", r"MEMBER\s*CONTRIBUTED"),
    ("_high_school", r"HIGH\s*SCHOOL\s*GRADUATE"),
    ("_leave", r"DAYS\s*ACCRUED\s*LEAVE"),
    ("_dental", r"DENTAL\s*EXAMINATION|MEMBER\s*WAS\s*PROVIDED"),
    ("_retirement", r"RETIREMENT\s*SYSTEM"),
    ("_dd214_1", r"DD\s*(?:FORM\s*)?214-1"),
    ("_remarks", r"\bREMARKS\b"),
    ("_mailing", r"MAILING\s*ADDRESS"),
    ("_relative", r"NEAREST\s*RELATIVE"),
    ("_va_copy", r"MEMBER\s*REQUESTS\s*COPY"),
    ("_member_signature", r"SIGNATURE\s*OF\s*MEMBER|MEMBER'?S\s*SIGNATURE"),
    ("_official", r"OFFICIAL\s*AUTHORIZED\s*TO\s*SIGN"),
    ("_special_info", r"SPECIAL\s*ADDITIONAL\s*INFORMATION"),
    ("_separation_type", r"TYPE\s*OF\s*SEPARATION"),
    ("_character", r"CHARACTER\s*OF\s*SERVICE"),
    ("_separation_authority", r"SEPARATION\s*AUTHORITY"),
    ("_separation_code", r"SEPARATION\s*CODE"),
    ("_reentry", r"REENTRY\s*CODE"),
    ("_narrative", r"NARRATIVE\s*REASON"),
    ("_time_lost", r"DATES\s*OF\s*TIME\s*LOST"),
]
_LABEL_RES = [(k, re.compile(p)) for k, p in LABELS]

BRANCHES: list[tuple[str, str]] = [  # checked in order; Marines before Navy, etc.
    ("Marine Corps", r"MARINE\s*CORPS|\bUSMC\b|\bUSMCR\b"),
    ("Space Force", r"SPACE\s*FORCE|\bUSSF\b"),
    ("Coast Guard", r"COAST\s*GUARD|\bUSCG\b|\bUSCGR\b"),
    ("Air Force", r"AIR\s*FORCE|\bUSAF\b|\bUSAFR\b|\bANG\b"),
    ("Army", r"\bARMY\b|\bUSAR\b|\bARNG\b|\bRA\b"),
    ("Navy", r"\bNAVY\b|\bUSN\b|\bUSNR\b"),
]

RANK_TO_PAY_GRADE: dict[str, str] = {
    # Army
    "PV1": "E1",
    "PVT": "E1",
    "PV2": "E2",
    "PFC": "E3",
    "SPC": "E4",
    "CPL": "E4",
    "SGT": "E5",
    "SSG": "E6",
    "SFC": "E7",
    "MSG": "E8",
    "1SG": "E8",
    "SGM": "E9",
    "CSM": "E9",
    "WO1": "W1",
    "CW2": "W2",
    "CW3": "W3",
    "CW4": "W4",
    "CW5": "W5",
    "2LT": "O1",
    "1LT": "O2",
    "CPT": "O3",
    "MAJ": "O4",
    "LTC": "O5",
    "COL": "O6",
    # Marine Corps
    "LCPL": "E3",
    "SSGT": "E6",
    "GYSGT": "E7",
    "MGYSGT": "E9",
    "SGTMAJ": "E9",
    "CAPT": "O3",
    "LTCOL": "O5",
    # Air / Space Force
    "AB": "E1",
    "AMN": "E2",
    "A1C": "E3",
    "SRA": "E4",
    "TSGT": "E6",
    "MSGT": "E7",
    "SMSGT": "E8",
    "CMSGT": "E9",
    "SPC1": "E1",
    "SPC2": "E2",
    "SPC3": "E3",
    "SPC4": "E4",
    "CAPTAIN": "O3",
    # Navy / Coast Guard
    "SR": "E1",
    "SA": "E2",
    "SN": "E3",
    "FN": "E3",
    "AN": "E3",
    "HN": "E3",
    "PO3": "E4",
    "PO2": "E5",
    "PO1": "E6",
    "CPO": "E7",
    "SCPO": "E8",
    "MCPO": "E9",
    "ENS": "O1",
    "LTJG": "O2",
    "LCDR": "O4",
    "CDR": "O5",
}

YEARS_UNIT = r"YEARS?|YRS?|YR\(S\)"
# "OS": OCR lost the M of "MOS" to the replacement character, which clean_ocr() drops.
MONTHS_UNIT = r"MONTHS?|MO\(S\)|MOS|MO|OS"
DURATION_RE = re.compile(
    rf"(?:(?P<y>\d{{1,2}})\s*(?:{YEARS_UNIT})\.?\s*,?\s*(?:AND\s*)?)?"
    rf"(?:(?P<m>\d{{1,2}})\s*(?:{MONTHS_UNIT})\b\.?)?"
)
# Same as DURATION_RE but never matches the empty string; safe for .sub().
DURATION_STRICT_RE = re.compile(
    rf"\d{{1,2}}\s*(?:{YEARS_UNIT})\.?(?:\s*,?\s*(?:AND\s*)?\d{{1,2}}\s*"
    rf"(?:{MONTHS_UNIT})\b\.?)?|\d{{1,2}}\s*(?:{MONTHS_UNIT})\b\.?"
)
# Every word a duration is written out of, so a line that holds nothing else is a piece of
# one: a block's box can wrap an entry anywhere, "23 YRS 5" and "MOS" included.
TIME_WORDS_RE = re.compile(rf"\d{{1,2}}|{YEARS_UNIT}|{MONTHS_UNIT}|AND")
# Longer than any career; a larger YEAR(S) value in block 12 is a misread, not a duration.
MAX_SERVICE_YEARS = 45
PAY_GRADE_RE = re.compile(r"\b([EOW])\s*-?\s*0?(10|[1-9])\b")
YEAR_RE = re.compile(r"\b(19[4-9]\d|20[0-4]\d)\b")
TRIPLE_RE = re.compile(r"\b(\d{1,4})\s+(\d{1,2})\s+(\d{1,2})\b")
NOTHING_FOLLOWS_RE = re.compile(r"/*\s*NOTHING\s*FOLLOWS\s*/*")
LONG_PAREN_RE = re.compile(r"\([^()]{25,}\)", re.DOTALL)
TRAILING_BLOCK_NUM_RE = re.compile(r"[\s|]*\b\d{1,2}\s*[A-J]?\s*\.?\s*$")
# A character the source could not read, and the control characters a text layer may carry.
# Dropped rather than kept, so one unreadable letter does not make its word unreadable.
UNREADABLE_RE = re.compile(r"[�\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]+")
# The "//" the form puts between entries, as OCR reads it when it cannot tell the strokes
# apart: "I I", "/ /", "| |", "1 1". Only between entries, never inside a word, so a mark
# pair needs whitespace around it and text either side of it.
ENTRY_SEPARATOR_RE = re.compile(r"(?<=[A-Z0-9)\].,])\s+[I1|/]\s+[I1|/]\s+(?=[A-Z0-9])", re.I)
# The form's own end-of-list marker, and the markers that send the reader to another block.
# Neither is a value. Matched on letters alone, because OCR garbles both.
NOTHING_FOLLOWS = "NOTHINGFOLLOWS"
MARKER_MATCH = 85
CONTINUATION_RE = re.compile(r"^(?:CONT|SEE)[A-Z]{0,8}?(?:BL|REMARK)")


# --------------------------------------------------------------------------- helpers


def clean_ocr(text: str) -> str:
    """`text` without the characters its source could not read."""
    return UNREADABLE_RE.sub("", text)


def _is_marker(entry: str) -> bool:
    """Whether an entry is the form's "NOTHING FOLLOWS" or a "continued in block 18"
    marker rather than a value, however OCR spelled it."""
    letters = re.sub(r"[^A-Z]", "", entry.upper())
    return (
        fuzz.ratio(letters, NOTHING_FOLLOWS) >= MARKER_MATCH
        or CONTINUATION_RE.match(letters) is not None
    )


def detect_version(text: str) -> str:
    t = text.upper()
    if re.search(
        r"CERTIFICATE\s*OF\s*UNIFORMED\s*SERVICE|DO[DW]\s*ID\s*NUMBER|UNIFORMED\s*"
        r"SERVICE\s*EDUCATION",
        t,
    ):
        return "2022"
    if re.search(
        r"CERTIFICATE\s*OF\s*RELEASE\s*OR\s*DISCHARGE|SOCIAL\s*SECURITY\s*NUMBER|"
        r"PRIMARY\s*SPECIALTY|MILITARY\s*EDUCATION",
        t,
    ):
        return "2000"
    return "unknown"


def segment(text: str) -> dict[str, str]:
    """Split DD-214 text into label-keyed segments (first occurrence of each label)."""
    t = LONG_PAREN_RE.sub(" ", text.upper())
    hits: list[tuple[int, int, str]] = []
    for key, rx in _LABEL_RES:
        m = rx.search(t)
        if m:
            hits.append((m.start(), m.end(), key))
    hits.sort()
    segs: dict[str, str] = {}
    for i, (_, end, key) in enumerate(hits):
        nxt = hits[i + 1][0] if i + 1 < len(hits) else len(t)
        val = TRAILING_BLOCK_NUM_RE.sub("", t[end : max(end, nxt)])
        val = re.sub(r"^\s*\([^)]*\)", "", val)  # leftover short label text, e.g. "(YYYYMMDD)"
        segs[key] = val.strip(" \t\r\n:.-|")
    segs["_head"] = t[: hits[0][0]] if hits else ""
    segs["_text"] = t
    return segs


def detect_branch(s: str) -> str | None:
    for name, pat in BRANCHES:
        if re.search(pat, s.upper()):
            return name
    return None


def normalize_pay_grade(s: str | None) -> str | None:
    if not s:
        return None
    m = PAY_GRADE_RE.search(s.upper())
    return f"{m.group(1)}{int(m.group(2))}" if m else None


def pay_grade_from_rank(s: str | None) -> str | None:
    if not s:
        return None
    for tok in re.findall(r"[A-Z0-9]+", s.upper()):
        if tok in RANK_TO_PAY_GRADE:
            return RANK_TO_PAY_GRADE[tok]
    return None


def parse_duration(s: str | None) -> Duration | None:
    """Parse 'YYYY MM DD' service durations (e.g. '0004 02 13') or '4 YRS 2 MOS'."""
    if not s:
        return None
    for m in TRIPLE_RE.finditer(s):
        y, mo, d = (int(g) for g in m.groups())
        if y <= MAX_SERVICE_YEARS and mo <= 12 and d <= 31:
            return Duration(y, mo, d)
    for m in DURATION_RE.finditer(s.upper()):
        if m.group("y") or m.group("m"):
            return Duration(int(m.group("y") or 0), int(m.group("m") or 0), 0)
    return None


def _split_entries(seg: str, *, allow_commas: bool = False) -> list[str]:
    """One block's text as its entries: whatever the form put between them ("//", however
    OCR read it, or ";"), and the line breaks the block's box wrapped them on."""
    seg = ENTRY_SEPARATOR_RE.sub("//", NOTHING_FOLLOWS_RE.sub(" ", clean_ocr(seg)))
    parts = re.split(r"//|;|\n", seg)
    if len(parts) == 1 and allow_commas:
        parts = re.split(r",(?![^()]*\))", seg)
    out = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip(" ,.-/")
        if len(re.sub(r"[^A-Z0-9]", "", p.upper())) < 3 or p.upper() in {"NONE", "N/A"}:
            continue
        if not _is_marker(p):
            out.append(p)
    return out


def _run_on_entries(part: str) -> list[str]:
    """`part` cut after each duration it holds, for a block that puts nothing between its
    entries: "0311 RIFLEMAN 3 YRS 0 MOS 3531 MOTOR VEHICLE OPERATOR 1 YR 6 MOS"."""
    out: list[str] = []
    last = 0
    for m in DURATION_RE.finditer(part):
        if (m.group("y") or m.group("m")) and m.end() > last:
            out.append(part[last : m.end()])
            last = m.end()
    return [*out, part[last:]]


def _is_time_only(part: str) -> bool:
    """Whether `part` is a time and nothing else: no entry, only a piece of one's duration."""
    return not re.sub(r"[^A-Z0-9]", "", TIME_WORDS_RE.sub("", part.upper()))


def _joined_entries(entries: Iterable[str]) -> list[str]:
    """`entries` with each wrapped tail joined back to the entry it came from. A block's box
    wraps an entry wherever the line runs out, so a line can hold the end of the entry
    above's time and nothing else: "11 YRS" then "2 MOS", or "23 YRS 5" then "MOS"."""
    raws: list[str] = []
    for entry in entries:
        raws.append(entry)
        # Fold a trailing time back while that lengthens the time of the entry before it,
        # or while it is only being gathered out of the pieces the wrap left.
        while len(raws) >= 2 and _is_time_only(raws[-1]):
            joined = f"{raws[-2]} {raws[-1]}"
            if not _is_time_only(raws[-2]) and parse_duration(joined) == parse_duration(raws[-2]):
                break
            raws[-2:] = [joined]
    return raws


def parse_specialties(seg: str | None) -> list[Specialty]:
    if not seg:
        return []
    split = (
        entry.strip()
        for part in _split_entries(seg.upper())
        for entry in _run_on_entries(part)
        if entry.strip()
    )
    entries = [
        Specialty(raw=raw, months=dur.total_months if (dur := parse_duration(raw)) else None)
        for raw in _joined_entries(split)
        if not _is_time_only(raw)
    ]
    # Drop what is no entry at all: a stray number, or a duration with nothing to time.
    return [e for e in entries if re.search(r"[A-Z]{2}", DURATION_STRICT_RE.sub("", e.raw))]


def parse_courses(seg: str | None) -> list[Course]:
    courses = []
    for part in _split_entries(seg or ""):
        u = part.upper()
        weeks = None
        if m := re.search(r"(\d+(?:\.\d+)?)\s*(?:WKS?|WEEKS?)\b", u):
            weeks = float(m.group(1))
        elif m := re.search(r"(\d+)\s*(?:DAYS?|DYS?)\b", u):
            weeks = round(int(m.group(1)) / 7, 1)
        elif m := re.search(r"(\d+)\s*(?:HRS?|HOURS?)\b", u):
            weeks = round(int(m.group(1)) / 40, 1)
        years = YEAR_RE.findall(u)
        title = re.sub(
            r"\(?\d+(?:\.\d+)?\s*(?:WKS?|WEEKS?|DAYS?|DYS?|HRS?|HOURS?)\)?\b|"
            r"\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?\b|"
            r"\b\d{1,2}/\d{2,4}\b|\b(?:19|20)\d{2}\b",
            " ",
            u,
        )
        title = canonical_course(re.sub(r"\s+", " ", title).strip(" ,.-()/"))
        if len(title) >= 3:
            courses.append(
                Course(raw=part, title=title, weeks=weeks, year=int(years[-1]) if years else None)
            )
    return courses


def parse_decorations(seg: str | None) -> list[str]:
    return [d.upper() for d in _split_entries(seg or "", allow_commas=True)]
