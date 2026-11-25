"""Command-line interface: dd214kw build-index | translate | lookup."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from rich.console import Console

from . import __version__
from .evidence import ServiceContext
from .extract import ExtractionError
from .extractors import read
from .index import DEFAULT_INDEX, Index, build_index, download
from .render import print_rich, to_ats, to_json, to_markdown
from .resolve import resolve
from .translate import ALL_PRIMARY, BRANCH_SVCS, translate

err = Console(stderr=True)


def _cmd_build(a: argparse.Namespace) -> int:
    if a.download:
        err.print(f"Downloading source data to {a.raw_dir} ...")
        download(a.raw_dir, log=err.print)
    err.print(f"Building index {a.index} ...")
    build_index(a.raw_dir, a.index, log=err.print)
    err.print(f"[green]Done:[/] {a.index}")
    return 0


def _cmd_translate(a: argparse.Namespace) -> int:
    try:
        doc, facts = read(a.file, ocr=a.ocr, json_input=a.json_input)
    except ExtractionError as e:
        err.print(f"[red]{e}[/]")
        return 2
    if a.branch:
        facts = [replace(f, branch=a.branch) if isinstance(f, ServiceContext) else f for f in facts]
    report = translate(Index(a.index), resolve(facts), top=a.top)
    report = replace(report, documents=[doc], warnings=[*doc.notes, *report.warnings])

    match a.format:
        case "json":
            out = to_json(report)
        case "md":
            out = to_markdown(report)
        case "ats":
            out = to_ats(report, a.limit)
        case _:
            if a.output:
                out = to_markdown(report)
            else:
                print_rich(report, explain=a.explain)
                return 0
    if a.output:
        a.output.write_text(out, encoding="utf-8")
        err.print(f"Wrote {a.output}")
    else:
        sys.stdout.write(out + "\n")
    return 0


def _cmd_lookup(a: argparse.Namespace) -> int:
    from .translate import _occupations

    idx = Index(a.index)
    svcs = BRANCH_SVCS.get(a.branch, ALL_PRIMARY) if a.branch else ALL_PRIMARY
    rows = idx.lookup_code(svcs, a.code)
    if not rows:
        err.print(f"[red]No code {a.code}[/] in {svcs}")
        return 1
    for r in rows:
        print(f"{r['svc']} {r['code']} [{r['mpc']}] {r['title']} status={r['status']}")
    for o in _occupations(idx, rows[0]["svc"], rows[0]["code"], rows[0]["title"]):
        print(f"  -> {o.onet} {o.title}  w={o.weight}  ({', '.join(o.sources)})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dd214kw", description=__doc__)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="SQLite index path")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build-index", help="Download O*NET/DMDC data and build the local index")
    b.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    b.add_argument("--download", action="store_true", help="Fetch any missing source files")
    b.set_defaults(func=_cmd_build)

    t = sub.add_parser("translate", help="Translate a DD-214 into civilian keywords")
    t.add_argument("file", type=Path, help="DD-214 as .pdf, .txt, image, or .json (pre-extracted)")
    t.add_argument("-f", "--format", choices=["rich", "md", "json", "ats"], default="rich")
    t.add_argument("-o", "--output", type=Path)
    t.add_argument("--top", type=int, default=12, help="Keywords per category")
    t.add_argument("--limit", type=int, default=40, help="ATS keyword count")
    t.add_argument("--explain", action="store_true", help="Show scores and sources")
    t.add_argument("--ocr", action="store_true", help="OCR scanned PDFs (needs 'ocr' extra)")
    t.add_argument("--json-input", action="store_true", help="Treat FILE as pre-extracted JSON")
    t.add_argument("--branch", choices=sorted(BRANCH_SVCS), help="Override detected branch")
    t.set_defaults(func=_cmd_translate)

    lk = sub.add_parser("lookup", help="Look up one military code in the crosswalk")
    lk.add_argument("code")
    lk.add_argument("--branch", choices=sorted(BRANCH_SVCS))
    lk.set_defaults(func=_cmd_lookup)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except FileNotFoundError as e:
        err.print(f"[red]{e}[/]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
