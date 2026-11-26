"""Read an OCR-garbled award or course name as the official name it stands for.

A scanner writes what it saw: "ARMY COMMEND A TL ON MEDAL" for the Army Commendation Medal,
"JOTKT SERVICE COMMENDA TL ON MEDAL" for the Joint Service Commendation Medal. Left as
they are, such names match no rule, and the same award reads as two on two documents.

The names are a data file each, `data/awards.csv` and `data/courses.csv`: the official name,
then the abbreviations a form may write instead ("ACM", "NCOPDR", "ANCOC"). A name is
matched on its letters alone, so spacing and punctuation noise do not count, and only above
SNAP_MATCH; below it the document's own text stands, because an official name the document
does not hold is a fact invented.
"""

from __future__ import annotations

import csv
import re
from functools import cache
from importlib import resources

from rapidfuzz import fuzz, process
from rapidfuzz.distance import Indel

# Fuzzy-match floor (0-100) for a name against the official names. Measured on the reported
# form: a garbled "JOINT MERITORIOUS UNIT AWARD" scores 83, and the nearest wrong match
# among the real award names tried, "GOLD STAR LAPEL BUTTON" against "ARMY LAPEL BUTTON",
# scores 77. Raising this leaves more names as the scanner spelled them; lowering it starts
# reading one award as another.
SNAP_MATCH = 82
# How much of what a name says the official name may leave unaccounted for, in characters
# and as a share of its length. See _accounts_for().
EXTRA_LETTERS, EXTRA_SHARE = 2, 0.15
# What an award was given with ("W/ 1 OAK LEAF CLUSTER", "WITH RIFLE BAR"): kept as the
# document words it, and left out of the match, which is against the award's own name.
DEVICE_RE = re.compile(r"\s+(?:W/|WITH)\s+.*$", re.S)
# A single letter is OCR noise as often as it is a word ("ARMY COMMEND A TL ON MEDAL"), so
# it counts on neither side of a match.
STRAY_LETTER_RE = re.compile(r"\b[A-Z]\b")


@cache
def _names(kind: str) -> tuple[tuple[str, str], ...]:
    """(letters to match, official name) for every name and abbreviation in `kind`.csv."""
    text = resources.files("dd214kw.data").joinpath(f"{kind}.csv").read_text(encoding="utf-8")
    out: list[tuple[str, str]] = []
    for row in csv.DictReader(text.splitlines()):
        written = [
            row["name"],
            *(a.strip() for a in (row["aliases"] or "").split(";") if a.strip()),
        ]
        out += [(_letters(name), row["name"]) for name in written]
    return tuple(out)


def _letters(text: str) -> str:
    return re.sub(r"[^A-Z]", "", STRAY_LETTER_RE.sub(" ", text.upper()))


def _accounts_for(written: str, official: str) -> bool:
    """Whether `official` accounts for what `written` says.

    A document may leave out what the official name holds, by abbreviating it or because
    OCR lost a word of it: "ARMY GOOD CONDUCT" is the Army Good Conduct Medal. But a name
    that says more than the official one is something else, something more specific: a
    course for leading petty officers is not the petty officer leadership course.
    """
    same = sum(
        op.src_end - op.src_start for op in Indel.opcodes(written, official) if op.tag == "equal"
    )
    return len(written) - same <= max(EXTRA_LETTERS, EXTRA_SHARE * len(written))


def _snap(text: str, kind: str) -> str:
    name = DEVICE_RE.sub("", text)
    device = text[len(name) :]
    written = _letters(name)
    names = _names(kind)
    best = process.extractOne(
        written,
        [letters for letters, _ in names],
        scorer=fuzz.ratio,
        score_cutoff=SNAP_MATCH,
    )
    if best is None or not _accounts_for(written, best[0]):
        return text
    return f"{names[best[2]][1]}{device}"


def canonical_award(name: str) -> str:
    """`name` as the official name of the decoration, medal, badge or ribbon it reads as."""
    return _snap(name, "awards")


def canonical_course(title: str) -> str:
    """`title` as the official name of the course it reads as."""
    return _snap(title, "courses")
