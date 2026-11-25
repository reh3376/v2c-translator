"""Output formats: rich terminal, Markdown, JSON, plain ATS keyword list."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import CATEGORIES, KeywordReport

ATTRIBUTION = (
    "Occupation data: O*NET 31.0 Database and DMDC Military Occupational Crosswalk, "
    "USDOL/ETA, CC BY 4.0."
)


def _summary(r: KeywordReport) -> list[str]:
    rec = r.record
    yrs = rec.net_active.total_months // 12 if rec.net_active else None
    return [
        f"Branch: {rec.branch or '?'}" + (f" ({rec.component})" if rec.component else ""),
        f"Pay grade: {rec.pay_grade or '?'}" + (f"  Rank: {rec.grade}" if rec.grade else ""),
        f"Net active service: {yrs} yrs" if yrs is not None else "Net active service: ?",
        f"DD-214 layout: {rec.form_version}",
    ]


def to_json(r: KeywordReport) -> str:
    d = r.to_dict()
    d["attribution"] = ATTRIBUTION
    return json.dumps(d, indent=2)


def to_ats(r: KeywordReport, limit: int = 40) -> str:
    return ", ".join(r.ats_keywords(limit))


def to_markdown(r: KeywordReport) -> str:
    lines = ["# Civilian Workforce Keywords", "", *[f"- {s}" for s in _summary(r)], ""]
    lines += [
        "## Military specialties",
        "",
        "| DD-214 entry | Matched code | Civilian occupations |",
        "|---|---|---|",
    ]
    for m in r.matches:
        occ = "; ".join(f"{o.title} ({o.onet})" for o in m.occupations[:5]) or "—"
        code = f"{m.code} {m.title}" if m.code else "not matched"
        lines.append(f"| {m.specialty.raw} | {code} | {occ} |")
    for cat, label in CATEGORIES.items():
        kws = r.keywords.get(cat) or []
        if kws:
            lines += ["", f"## {label}", "", ", ".join(k.term for k in kws)]
    lines += ["", "## ATS keyword string", "", to_ats(r)]
    if r.warnings:
        lines += ["", "## Notes", "", *[f"- {w}" for w in r.warnings]]
    lines += ["", f"_{ATTRIBUTION}_", ""]
    return "\n".join(lines)


def print_rich(r: KeywordReport, console: Console | None = None, explain: bool = False) -> None:
    c = console or Console()
    c.print(Panel("\n".join(_summary(r)), title="DD-214 → Civilian Keywords", expand=False))

    t = Table(title="Military specialties", show_lines=False)
    t.add_column("DD-214 entry")
    t.add_column("Matched")
    t.add_column("Civilian occupations (O*NET)")
    for m in r.matches:
        code = f"[bold]{m.code}[/] {m.title}\n[dim]{m.method}[/]" if m.code else "[red]no match[/]"
        occ = "\n".join(f"{o.title} [dim]{o.onet} w={o.weight}[/]" for o in m.occupations[:6])
        t.add_row(m.specialty.raw, code, occ or "—")
    c.print(t)

    for cat, label in CATEGORIES.items():
        kws = r.keywords.get(cat) or []
        if not kws:
            continue
        kt = Table(title=label, title_justify="left", show_header=explain, box=None, pad_edge=False)
        kt.add_column("Keyword", style="bold")
        if explain:
            kt.add_column("Score", justify="right")
            kt.add_column("Why", style="dim")
            for k in kws:
                kt.add_row(k.term, f"{k.score:.2f}", "; ".join(k.sources))
        else:
            kt.add_row(", ".join(k.term for k in kws))
        c.print(kt)
        c.print()

    c.print(Panel(to_ats(r), title="ATS keyword string", expand=False))
    for w in r.warnings:
        c.print(f"[yellow]! {w}[/]")
    c.print(f"[dim]{ATTRIBUTION}[/]")
