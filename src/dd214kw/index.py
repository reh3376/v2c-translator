"""Build and query the local SQLite index (DMDC military crosswalk + O*NET database).

All sources are public (O*NET / DMDC, CC BY 4.0). Attribution: "This product includes
information from O*NET OnLine by the U.S. Department of Labor, Employment and Training
Administration (USDOL/ETA). Used under the CC BY 4.0 license."
"""

from __future__ import annotations

import csv
import math
import os
import sqlite3
import zipfile
from collections import defaultdict
from collections.abc import Callable, Iterator
from functools import cache
from importlib import resources
from pathlib import Path

DEFAULT_INDEX = Path(
    os.environ.get("DD214KW_INDEX", Path.home() / ".local" / "share" / "dd214kw" / "index.sqlite")
)

ONET = "https://www.onetcenter.org"
DOWNLOADS: dict[str, str] = {
    "military_crosswalk.zip": f"{ONET}/dl_files/2019/military_crosswalk.zip",
    "cool_supplemental_data.xlsx": f"{ONET}/dl_files/2019/cool_supplemental_data.xlsx",
    "citm_supplemental_data.xlsx": f"{ONET}/dl_files/2019/citm_supplemental_data.xlsx",
    "db_31_0_text.zip": f"{ONET}/dl_files/database/db_31_0_text.zip",
}

# How much each crosswalk source is trusted when weighting civilian occupations. "vmet"
# links come from the member's own VMET at translate time, not from the index.
# (The 2010 Army KSA crosswalk is not used: it fans out to ~80-190 occupations per MOS.)
LINK_WEIGHTS = {"dmdc": 1.0, "cool": 0.7, "citm": 0.5, "vmet": 0.9}
ANALOG_WEIGHT = 0.5  # civilian analogs substituted for military-only SOC 55-xxxx codes

SCHEMA = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE moc(svc TEXT, code TEXT, mpc TEXT, title TEXT, status TEXT, sdate TEXT, edate TEXT);
CREATE INDEX moc_code ON moc(code);
CREATE TABLE moc_onet(svc TEXT, code TEXT, status TEXT, onet TEXT, source TEXT, weight REAL);
CREATE INDEX moc_onet_k ON moc_onet(svc, code);
CREATE TABLE analog(military_onet TEXT, civilian_onet TEXT, note TEXT);
CREATE TABLE occupation(onet TEXT PRIMARY KEY, title TEXT, description TEXT, job_zone INTEGER);
CREATE TABLE occ_title(onet TEXT, title TEXT, featured INTEGER);
CREATE INDEX occ_title_k ON occ_title(onet);
CREATE TABLE occ_element(onet TEXT, kind TEXT, name TEXT, importance REAL, distinct_score REAL);
CREATE INDEX occ_element_k ON occ_element(onet, kind);
CREATE TABLE occ_tech(onet TEXT, example TEXT, category TEXT, hot INTEGER, in_demand INTEGER,
                       idf REAL);
CREATE INDEX occ_tech_k ON occ_tech(onet);
CREATE TABLE occ_dwa(onet TEXT, dwa TEXT, score REAL);
CREATE INDEX occ_dwa_k ON occ_dwa(onet);
"""


# --------------------------------------------------------------------------- build


def download(raw_dir: Path, log: Callable[[str], None] = print) -> None:
    import httpx

    raw_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=180) as client:
        for name, url in DOWNLOADS.items():
            dest = raw_dir / name
            if dest.exists():
                log(f"  have {name}")
                continue
            r = client.get(url)
            r.raise_for_status()
            dest.write_bytes(r.content)
            log(f"  downloaded {name} ({len(r.content):,} bytes)")
            if dest.suffix == ".zip":
                with zipfile.ZipFile(dest) as z:
                    z.extractall(raw_dir / dest.stem)


def _find(raw_dir: Path, pattern: str) -> Path:
    hits = sorted(raw_dir.rglob(pattern))
    if not hits:
        raise FileNotFoundError(f"{pattern} not found under {raw_dir} (run with --download)")
    return hits[-1]


def _tsv(path: Path) -> Iterator[dict[str, str]]:
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        yield from csv.DictReader(f, delimiter="\t")


def _xlsx_rows(path: Path, sheet_contains: str | None = None) -> Iterator[dict[str, str]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = next((wb[n] for n in wb.sheetnames if sheet_contains and sheet_contains in n), wb.active)
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows)]
    for r in rows:
        yield {h: ("" if v is None else str(v).strip()) for h, v in zip(header, r, strict=False)}


def build_index(raw_dir: Path, out: Path, log: Callable[[str], None] = print) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)

    # ---- DMDC military crosswalk
    milx = _find(raw_dir, "milx*.csv")
    moc_rows, link_rows = [], []
    with milx.open(encoding="latin-1", newline="") as f:
        for r in csv.DictReader(f):
            svc, code = r["SVC"].strip(), r["MOC"].strip().upper()
            status = r["STATUS"].strip()
            moc_rows.append(
                (
                    svc,
                    code,
                    r["MPC"].strip(),
                    r["MOC_TITLE"].strip(),
                    status,
                    r["SDATE"].strip(),
                    r["EDATE"].strip(),
                )
            )
            for i in range(1, 5):
                onet = (r.get(f"ONET{i}") or "").strip()
                if onet:
                    link_rows.append((svc, code, status, onet, "dmdc", LINK_WEIGHTS["dmdc"]))
    log(f"  DMDC crosswalk: {len(moc_rows):,} codes, {len(link_rows):,} links ({milx.name})")

    # ---- Supplemental crosswalks
    for source, fname, sheet, code_col, svc_col in [
        ("cool", "cool_supplemental_data.xlsx", "Links", "Code", "SVC"),
        ("citm", "citm_supplemental_data.xlsx", "Links", "Code", "SVC"),
    ]:
        try:
            path = _find(raw_dir, fname)
        except FileNotFoundError:
            log(f"  (skipping {fname}: not found)")
            continue
        n = 0
        for r in _xlsx_rows(path, sheet):
            code, onet = r.get(code_col, "").upper(), r.get("O*NET-SOC Code", "")
            if code and onet:
                svc = r.get(svc_col, "") if svc_col else "A"
                link_rows.append((svc, code, "A", onet, source, LINK_WEIGHTS[source]))
                n += 1
        log(f"  {source}: {n:,} links")
    con.executemany("INSERT INTO moc VALUES (?,?,?,?,?,?,?)", moc_rows)
    con.executemany("INSERT INTO moc_onet VALUES (?,?,?,?,?,?)", link_rows)

    # ---- Curated civilian analogs for military-only SOC 55 occupations
    analog_csv = resources.files("dd214kw.data").joinpath("analog_55.csv").read_text()
    analogs = [
        (r["military_onet"], r["civilian_onet"], r["note"])
        for r in csv.DictReader(analog_csv.splitlines())
    ]
    con.executemany("INSERT INTO analog VALUES (?,?,?)", analogs)

    # ---- O*NET database
    onet_dir = _find(raw_dir, "Occupation Data.txt").parent
    zones = {r["O*NET-SOC Code"]: int(r["Job Zone"]) for r in _tsv(onet_dir / "Job Zones.txt")}
    occ = [
        (r["O*NET-SOC Code"], r["Title"], r["Description"], zones.get(r["O*NET-SOC Code"]))
        for r in _tsv(onet_dir / "Occupation Data.txt")
    ]
    con.executemany("INSERT INTO occupation VALUES (?,?,?,?)", occ)
    valid = {o[0] for o in occ}
    bad = sorted({a[1] for a in analogs} - valid)
    if bad:
        log(f"  WARNING: analog codes not in O*NET {onet_dir.name}: {', '.join(bad)}")

    titles = [(o[0], o[1], 2) for o in occ]
    titles += [
        (
            r["O*NET-SOC Code"],
            r["Reported Job Title"],
            1 if r.get("Shown in My Next Move") == "Y" else 0,
        )
        for r in _tsv(onet_dir / "Sample of Reported Titles.txt")
    ]
    con.executemany("INSERT INTO occ_title VALUES (?,?,?)", titles)

    for kind, fname in [("skill", "Transferable Skills.txt"), ("knowledge", "Knowledge.txt")]:
        rows = [
            (r["O*NET-SOC Code"], r["Element Name"], float(r["Data Value"]))
            for r in _tsv(onet_dir / fname)
            if r["Scale ID"] == "IM" and r.get("Recommend Suppress") != "Y"
        ]
        by_el: dict[str, list[float]] = defaultdict(list)
        for _, name, v in rows:
            by_el[name].append(v)
        mean = {k: sum(v) / len(v) for k, v in by_el.items()}
        con.executemany(
            "INSERT INTO occ_element VALUES (?,?,?,?,?)",
            [(o, kind, n, v, round(v - mean[n], 4)) for o, n, v in rows],
        )
        log(f"  O*NET {kind}: {len(rows):,} ratings")

    tech = [
        (
            r["O*NET-SOC Code"],
            r["Workplace Example"],
            r["Element Name"],
            int(r["Hot Technology"] == "Y"),
            int(r["In Demand"] == "Y"),
        )
        for r in _tsv(onet_dir / "Software Skills.txt")
    ]
    # Inverse document frequency so ubiquitous tools (MS Office) don't crowd out specific ones.
    df: dict[str, int] = defaultdict(int)
    for t in tech:
        df[t[1]] += 1
    max_idf = math.log(len(occ) / 1)
    con.executemany(
        "INSERT INTO occ_tech VALUES (?,?,?,?,?,?)",
        [(*t, round(math.log(len(occ) / df[t[1]]) / max_idf, 4)) for t in tech],
    )

    task_type = {
        (r["O*NET-SOC Code"], r["Task ID"]): r["Task Type"]
        for r in _tsv(onet_dir / "Task Statements.txt")
    }
    task_imp = {
        (r["O*NET-SOC Code"], r["Task ID"]): float(r["Data Value"])
        for r in _tsv(onet_dir / "Task Ratings.txt")
        if r["Scale ID"] == "IM"
    }
    dwa_name = {
        r["DWA Element ID"]: r["DWA Element Name"].rstrip(".")
        for r in _tsv(onet_dir / "GWAs to IWAs to DWAs.txt")
    }
    dwa_score: dict[tuple[str, str], float] = {}
    for r in _tsv(onet_dir / "Tasks to DWAs.txt"):
        key = (r["O*NET-SOC Code"], r["Task ID"])
        name = dwa_name.get(r["DWA Element ID"])
        if not name:
            continue
        s = task_imp.get(key, 3.0) * (1.0 if task_type.get(key) == "Core" else 0.6)
        k2 = (key[0], name)
        dwa_score[k2] = max(dwa_score.get(k2, 0.0), s)
    con.executemany(
        "INSERT INTO occ_dwa VALUES (?,?,?)", [(o, n, s) for (o, n), s in dwa_score.items()]
    )
    log(
        f"  O*NET: {len(occ):,} occupations, {len(tech):,} technology links, "
        f"{len(dwa_score):,} work-activity links"
    )

    con.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [("crosswalk_file", milx.name), ("onet_release", onet_dir.name)],
    )
    con.commit()
    con.close()
    tmp.replace(out)


# --------------------------------------------------------------------------- query


class Index:
    def __init__(self, path: Path = DEFAULT_INDEX):
        if not path.exists():
            raise FileNotFoundError(
                f"Index not found at {path}. Build it first: dd214kw build-index --download"
            )
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row

    def meta(self) -> dict[str, str]:
        return {r["key"]: r["value"] for r in self.con.execute("SELECT * FROM meta")}

    def lookup_code(self, svcs: list[str], code: str) -> list[sqlite3.Row]:
        q = (
            f"SELECT * FROM moc WHERE code = ? AND svc IN ({','.join('?' * len(svcs))}) "
            "ORDER BY status = 'A' DESC, sdate DESC"
        )
        return self.con.execute(q, [code.upper(), *svcs]).fetchall()

    @cache  # noqa: B019 - index lives for the process
    def titles_for(self, svcs: tuple[str, ...]) -> list[tuple[str, str, str, str]]:
        q = (
            f"SELECT svc, code, title, status FROM moc WHERE svc IN "
            f"({','.join('?' * len(svcs))}) AND title <> '' ORDER BY status = 'A' DESC"
        )
        return [tuple(r) for r in self.con.execute(q, svcs)]

    def links(self, svc: str, code: str) -> list[tuple[str, str, float]]:
        rows = self.con.execute(
            "SELECT onet, source, weight, status FROM moc_onet WHERE svc = ? AND code = ?",
            (svc, code.upper()),
        ).fetchall()
        dmdc_active = [r for r in rows if r["source"] == "dmdc" and r["status"] == "A"]
        keep = [r for r in rows if r["source"] != "dmdc"] + (
            dmdc_active or [r for r in rows if r["source"] == "dmdc"]
        )
        return [(r["onet"], r["source"], r["weight"]) for r in keep]

    def analogs(self, military_onet: str) -> list[str]:
        return [
            r[0]
            for r in self.con.execute(
                "SELECT civilian_onet FROM analog WHERE military_onet = ?", (military_onet,)
            )
        ]

    def occupation(self, onet: str) -> sqlite3.Row | None:
        return self.con.execute("SELECT * FROM occupation WHERE onet = ?", (onet,)).fetchone()

    def occ_titles(self, onet: str) -> list[sqlite3.Row]:
        return self.con.execute(
            "SELECT title, featured FROM occ_title WHERE onet = ? AND featured > 0", (onet,)
        ).fetchall()

    def elements(self, onet: str, kind: str) -> list[sqlite3.Row]:
        return self.con.execute(
            "SELECT name, importance, distinct_score FROM occ_element WHERE onet = ? AND kind = ?",
            (onet, kind),
        ).fetchall()

    def tech(self, onet: str) -> list[sqlite3.Row]:
        return self.con.execute("SELECT * FROM occ_tech WHERE onet = ?", (onet,)).fetchall()

    def dwas(self, onet: str) -> list[sqlite3.Row]:
        return self.con.execute("SELECT dwa, score FROM occ_dwa WHERE onet = ?", (onet,)).fetchall()
