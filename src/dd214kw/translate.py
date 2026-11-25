"""Profile -> civilian occupations -> ranked workforce keywords."""

from __future__ import annotations

import math
import re
from collections import defaultdict

from rapidfuzz import fuzz, process

from .evidence import OccupationHeld
from .index import ANALOG_WEIGHT, Index
from .models import (
    CATEGORIES,
    Keyword,
    KeywordReport,
    OccupationLink,
    SpecialtyMatch,
)
from .resolve import Profile
from .rules import rule_keywords

# Crosswalk SVC codes searched for each branch (primary codes first). See data-sources.md.
BRANCH_SVCS: dict[str, list[str]] = {
    "Army": ["A", "J", "Q"],
    "Air Force": ["F", "H", "Y", "X"],
    "Space Force": ["H", "F", "U", "L"],
    "Marine Corps": ["M"],
    "Navy": ["N", "P", "V", "S"],
    "Coast Guard": ["C"],
}
ALL_PRIMARY = ["A", "F", "H", "M", "N", "C", "P"]

MAX_OCCUPATIONS_PER_SPECIALTY = 8
MIN_ELEMENT_IMPORTANCE = 3.0  # O*NET 1-5 importance scale
TITLE_MATCH_CUTOFF = 88


# --------------------------------------------------------------------------- matching


def _candidate_codes(raw: str, code: str | None = None) -> list[str]:
    u = raw.upper()
    toks: list[str] = [code.strip().upper()] if code else []
    toks += re.findall(r"\(([A-Z]{2,4})\)", u)  # "ELECTRONICS TECHNICIAN (ET)"
    toks += re.findall(r"^\s*([A-Z]{2,4})\s*[-\u2013/:]", u)  # "ET - ELECTRONICS TECHNICIAN"
    toks += [t for t in re.findall(r"\b[A-Z0-9]{3,8}\b", u) if re.search(r"\d", t)]
    return list(dict.fromkeys(toks))


def _variants(tok: str) -> list[tuple[str, str]]:
    out = [(tok, "code")]
    # Air/Space Force AFSC: swap the skill-level digit (3D172 -> 3D152, 3D132 ...).
    if m := re.fullmatch(r"([A-Z]?\d[A-Z]\d)([0-9X])(\d[A-Z]?)", tok):
        out += [(m.group(1) + lvl + m.group(3), "code-variant") for lvl in "5739X10"]
    # Army MOS with skill level / SQI suffix: 11B10 -> 11B, 153A0 -> 153A.
    if m := re.fullmatch(r"(\d{2,3}[A-Z])[0-9A-Z]{1,3}", tok):
        out.append((m.group(1), "code-variant"))
    return out


def _clean_title(raw: str) -> str:
    u = raw.upper()
    u = re.sub(r"\b[A-Z0-9]*\d[A-Z0-9]*\b|\([A-Z]{2,4}\)", " ", u)
    u = re.sub(
        r"\b(FIRST|SECOND|THIRD) CLASS\b|\bPETTY OFFICER\b|\bPRIMARY\b|\bMOS\b|\bAFSC\b|"
        r"\bRATING\b|\bNEC\b",
        " ",
        u,
    )
    return re.sub(r"[^A-Z&/ ]", " ", re.sub(r"\s+", " ", u)).strip()


def match_specialty(
    index: Index, spec: OccupationHeld, branch: str | None, pay_grade: str | None
) -> SpecialtyMatch:
    svcs = BRANCH_SVCS.get(branch or "", ALL_PRIMARY)
    mpc = pay_grade[0] if pay_grade else None
    result = SpecialtyMatch(specialty=spec)

    for tok in _candidate_codes(spec.title, spec.code):
        for code, method in _variants(tok):
            rows = index.lookup_code(svcs, code)
            if mpc:
                rows = [r for r in rows if r["mpc"] == mpc] or rows
            if rows:
                r = rows[0]
                result.svc, result.code, result.title, result.method = (
                    r["svc"],
                    r["code"],
                    r["title"],
                    method,
                )
                return result

    title = _clean_title(spec.title)
    if len(title) >= 4:
        choices = index.titles_for(tuple(svcs))
        best = process.extractOne(
            title,
            [c[2].upper() for c in choices],
            scorer=fuzz.token_sort_ratio,
            score_cutoff=TITLE_MATCH_CUTOFF,
        )
        if best:
            svc, code, t, _ = choices[best[2]]
            result.svc, result.code, result.title, result.method = svc, code, t, "title"
    return result


def _occupations(index: Index, svc: str, code: str, moc_title: str = "") -> list[OccupationLink]:
    links_raw = index.links(svc, code)
    fanout: dict[str, int] = defaultdict(int)
    for _, source, _ in links_raw:
        fanout[source] += 1

    acc: dict[str, tuple[list[float], list[str]]] = defaultdict(lambda: ([], []))
    for onet, source, w in links_raw:
        if source != "dmdc":
            # Supplemental sources sometimes list dozens of loosely related occupations;
            # decay by fan-out so a long list can't swamp the DMDC link.
            w /= math.sqrt(max(1.0, fanout[source] / 4))
        if onet.startswith("55-"):  # military-only SOC: substitute curated civilian analogs
            for civ in index.analogs(onet):
                acc[civ][0].append(w * ANALOG_WEIGHT)
                acc[civ][1].append(f"{source}:analog-of-{onet}")
        else:
            acc[onet][0].append(w)
            acc[onet][1].append(source)
    links = []
    for onet, (ws, srcs) in acc.items():
        occ = index.occupation(onet)
        if not occ:
            continue
        weight = min(max(ws) + 0.15 * (len(set(srcs)) - 1), 1.2)
        if moc_title and "dmdc" not in srcs:
            # Tie-break supplemental links by title similarity to the military job.
            rel = fuzz.token_set_ratio(moc_title.upper(), occ["title"].upper()) / 100
            weight *= 0.7 + 0.3 * rel
        links.append(
            OccupationLink(
                onet=onet, title=occ["title"], weight=round(weight, 3), sources=sorted(set(srcs))
            )
        )
    links.sort(key=lambda o: o.weight, reverse=True)
    return links[:MAX_OCCUPATIONS_PER_SPECIALTY]


# --------------------------------------------------------------------------- keywords


class _Acc:
    def __init__(self) -> None:
        self.score: dict[str, float] = defaultdict(float)
        self.label: dict[str, str] = {}
        self.src: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def add(self, term: str, score: float, source: str) -> None:
        if score <= 0 or not term:
            return
        k = term.casefold()
        self.score[k] += score
        self.label.setdefault(k, term)
        self.src[k][source] += score

    def top(self, cat: str, n: int) -> list[Keyword]:
        if not self.score:
            return []
        hi = max(self.score.values())
        ranked = sorted(self.score.items(), key=lambda kv: kv[1], reverse=True)[:n]
        return [
            Keyword(
                term=self.label[k],
                category=cat,
                score=round(s / hi, 3),
                sources=[x for x, _ in sorted(self.src[k].items(), key=lambda kv: -kv[1])][:3],
            )
            for k, s in ranked
        ]


def translate(index: Index, profile: Profile, top: int = 12) -> KeywordReport:
    ctx = profile.context
    warnings = [c.message for c in profile.conflicts]
    matches: list[SpecialtyMatch] = []
    for occ in profile.occupations:
        m = match_specialty(index, occ.value, ctx and ctx.branch, ctx and ctx.pay_grade)
        if m.code:
            m.occupations = _occupations(index, m.svc, m.code, m.title or "")
            if not m.occupations:
                warnings.append(
                    f"'{m.code} {m.title}' has no civilian crosswalk link "
                    "(often a skill identifier rather than a primary specialty)."
                )
        else:
            warnings.append(f"Could not match specialty: '{occ.value.title}'")
        matches.append(m)

    # Weight specialties by time in specialty (sqrt softens dominance of the longest one).
    known = [m.specialty.months for m in matches if m.specialty.months]
    default_months = (sum(known) / len(known)) if known else 12
    total = sum((m.specialty.months or default_months) for m in matches) or 1
    occ_w: dict[str, float] = defaultdict(float)
    occ_title: dict[str, str] = {}
    for m in matches:
        share = math.sqrt((m.specialty.months or default_months) / total)
        for o in m.occupations:
            occ_w[o.onet] += share * o.weight
            occ_title[o.onet] = o.title
    if occ_w:
        hi = max(occ_w.values())
        occ_w = {k: v / hi for k, v in occ_w.items()}

    cats = {c: _Acc() for c in CATEGORIES}
    for onet, w in occ_w.items():
        src = occ_title[onet]
        occ = index.occupation(onet)
        cats["job_titles"].add(occ["title"], w, f"O*NET {onet}")
        for t in index.occ_titles(onet):
            if t["featured"] == 1:
                cats["job_titles"].add(t["title"], w * 0.8, src)
        for kind, cat in (("skill", "skills"), ("knowledge", "knowledge")):
            for e in index.elements(onet, kind):
                if e["importance"] >= MIN_ELEMENT_IMPORTANCE and e["distinct_score"] > 0:
                    cats[cat].add(e["name"], w * e["distinct_score"], src)
        for t in index.tech(onet):
            boost = (1 + t["hot"] + t["in_demand"]) / 3
            cats["technologies"].add(t["example"], w * boost * (0.3 + 0.7 * t["idf"]), src)
        for d in index.dwas(onet):
            cats["work_activities"].add(d["dwa"], w * d["score"] / 5, src)

    keywords = {c: cats[c].top(c, top) for c in CATEGORIES}

    # Merge rule-based keywords (pay grade, courses, awards, service time).
    for kw in rule_keywords(profile):
        bucket = keywords.setdefault(kw.category, [])
        existing = next((k for k in bucket if k.term.casefold() == kw.term.casefold()), None)
        if existing:
            existing.score = max(existing.score, kw.score)
            existing.sources = list(dict.fromkeys(existing.sources + kw.sources))[:4]
        else:
            bucket.append(kw)
    for c in keywords:
        keywords[c] = sorted(keywords[c], key=lambda k: k.score, reverse=True)[: max(top, 1) + 6]

    if profile.occupations and not occ_w:
        warnings.append("No civilian occupations found; keywords come from rules only.")
    return KeywordReport(profile=profile, matches=matches, keywords=keywords, warnings=warnings)
