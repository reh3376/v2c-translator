"""Command-line interface: dd214kw build-index | translate | lookup | inspect-layout."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

from rich.console import Console

from . import __version__
from .evidence import Document, Fact, ServiceContext
from .extract import ExtractionError
from .extractors import read
from .index import DEFAULT_INDEX, Index, build_index, download
from .render import print_rich, to_ats, to_bundle, to_json, to_markdown
from .resolve import resolve
from .translate import ALL_PRIMARY, BRANCH_SVCS, translate

err = Console(stderr=True)


def _pages(raw: str) -> int:
    """`--max-pages`, which has to be a page count. Zero would refuse every document."""
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("a page limit is at least 1; leave it out for no limit")
    return value


def _cmd_build(a: argparse.Namespace) -> int:
    if a.download:
        err.print(f"Downloading source data to {a.raw_dir} ...")
        download(a.raw_dir, log=err.print)
    err.print(f"Building index {a.index} ...")
    build_index(a.raw_dir, a.index, log=err.print)
    err.print(f"[green]Done:[/] {a.index}")
    return 0


def _cmd_translate(a: argparse.Namespace) -> int:
    documents: list[Document] = []
    facts: list[Fact] = []
    for path in a.files:
        try:
            doc, doc_facts = read(path, ocr=a.ocr, json_input=a.json_input, max_pages=a.max_pages)
        except ExtractionError as e:
            err.print(f"[red]{path}: {e}[/]")
            return 2
        documents.append(doc)
        facts += doc_facts
    if a.branch:
        facts = [replace(f, branch=a.branch) if isinstance(f, ServiceContext) else f for f in facts]
    report = translate(Index(a.index), resolve(facts), top=a.top)
    notes = [n for d in documents for n in d.notes]
    report = replace(report, documents=documents, warnings=[*notes, *report.warnings])

    match a.format:
        case "json":
            out = to_json(report)
        case "md":
            out = to_markdown(report)
        case "json+md":
            out = to_bundle(report)
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


def _cmd_inspect(a: argparse.Namespace) -> int:
    from .inspect_layout import inspect, report, write_png

    try:
        result = inspect(a.file, ocr=a.ocr)
    except ExtractionError as e:
        err.print(f"[red]{e}[/]")  # no file name: it may hold the person's name
        return 2
    text = "\n".join(report(result)) + "\n"
    if a.output:
        a.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if a.png:
        write_png(result, a.png)
    written = " and ".join(str(p) for p in (a.output, a.png) if p)
    err.print(
        (f"Wrote {written}. " if written else "")
        + "It holds boxes, shape codes and our label ids, and no text from the document. "
        "Look it over before you share it."
    )
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

    t = sub.add_parser("translate", help="Translate one person's documents into civilian keywords")
    t.add_argument(
        "files",
        nargs="+",
        type=Path,
        metavar="FILE",
        help="One person's DD-214s (.pdf, .txt, image, or pre-extracted .json), DD-215s (.json) "
        "and VMET (.pdf, .txt)",
    )
    t.add_argument(
        "-f",
        "--format",
        choices=["rich", "md", "json", "ats", "json+md"],
        default="rich",
        help="json+md prints both in one envelope, from one reading of the documents",
    )
    t.add_argument("-o", "--output", type=Path)
    t.add_argument("--top", type=int, default=12, help="Keywords per category")
    t.add_argument("--limit", type=int, default=40, help="ATS keyword count")
    t.add_argument("--explain", action="store_true", help="Show scores and sources")
    t.add_argument("--ocr", action="store_true", help="OCR scanned PDFs (needs 'ocr' extra)")
    t.add_argument(
        "--max-pages",
        type=_pages,
        metavar="N",
        help="Refuse a document longer than N pages, counted before any page is read. "
        "No limit by default",
    )
    t.add_argument("--json-input", action="store_true", help="Treat FILE as pre-extracted JSON")
    t.add_argument("--branch", choices=sorted(BRANCH_SVCS), help="Override detected branch")
    t.set_defaults(func=_cmd_translate)

    lk = sub.add_parser("lookup", help="Look up one military code in the crosswalk")
    lk.add_argument("code")
    lk.add_argument("--branch", choices=sorted(BRANCH_SVCS))
    lk.set_defaults(func=_cmd_lookup)

    ins = sub.add_parser(
        "inspect-layout",
        help="Print a DD-214 page's geometry, with no text from it, to share for calibration",
    )
    ins.add_argument("file", type=Path, metavar="FILE", help="The DD-214 (.pdf or image)")
    ins.add_argument("--ocr", action="store_true", help="OCR a scan with no text layer")
    ins.add_argument("-o", "--output", type=Path, help="Write the text here, not to stdout")
    ins.add_argument("--png", type=Path, help="Also draw the geometry as a picture here")
    ins.set_defaults(func=_cmd_inspect)

    a = p.parse_args(argv)
    try:
        return a.func(a)
    except FileNotFoundError as e:
        err.print(f"[red]{e}[/]")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
