"""Output formats: rich terminal, Markdown, JSON, plain ATS keyword list."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .evidence import DOC_LABELS
from .models import CATEGORIES, KeywordReport

ATTRIBUTION = (
    "Occupation data: O*NET 31.0 Database and DMDC Military Occupational Crosswalk, "
    "USDOL/ETA, CC BY 4.0."
)


def _documents(r: KeywordReport) -> str:
    """How the report names the documents read, e.g. in a table header."""
    return " / ".join(dict.fromkeys(DOC_LABELS[d.doc_type] for d in r.documents)) or "Document"


def _summary(r: KeywordReport) -> list[str]:
    ctx = r.profile.context
    branch, component, pay_grade, rank = (
        (ctx.branch, ctx.component, ctx.pay_grade, ctx.rank) if ctx else (None,) * 4
    )
    net = r.profile.service_time.get("net_active")
    yrs = net.total_months // 12 if net else None
    return [
        f"Branch: {branch or '?'}" + (f" ({component})" if component else ""),
        f"Pay grade: {pay_grade or '?'}" + (f"  Rank: {rank}" if rank else ""),
        f"Net active service: {yrs} yrs" if yrs is not None else "Net active service: ?",
        *(f"{DOC_LABELS[d.doc_type]} layout: {d.layout}" for d in r.documents),
    ]


def to_json(r: KeywordReport) -> str:
    d = r.to_dict()
    d["attribution"] = ATTRIBUTION
    return json.dumps(d, indent=2, default=str)  # dates as ISO strings


def to_ats(r: KeywordReport, limit: int = 40) -> str:
    return ", ".join(r.ats_keywords(limit))


def to_markdown(r: KeywordReport) -> str:
    lines = ["# Civilian Workforce Keywords", "", *[f"- {s}" for s in _summary(r)], ""]
    lines += [
        "## Military specialties",
        "",
        f"| {_documents(r)} entry | Matched code | Civilian occupations |",
        "|---|---|---|",
    ]
    for m in r.matches:
        occ = "; ".join(f"{o.title} ({o.onet})" for o in m.occupations[:5]) or "—"
        code = f"{m.code} {m.title}" if m.code else "not matched"
        lines.append(f"| {m.specialty.title} | {code} | {occ} |")
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
    docs = _documents(r)
    c.print(Panel("\n".join(_summary(r)), title=f"{docs} → Civilian Keywords", expand=False))

    t = Table(title="Military specialties", show_lines=False)
    t.add_column(f"{docs} entry")
    t.add_column("Matched")
    t.add_column("Civilian occupations (O*NET)")
    for m in r.matches:
        code = f"[bold]{m.code}[/] {m.title}\n[dim]{m.method}[/]" if m.code else "[red]no match[/]"
        occ = "\n".join(f"{o.title} [dim]{o.onet} w={o.weight}[/]" for o in m.occupations[:6])
        t.add_row(m.specialty.title, code, occ or "—")
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
