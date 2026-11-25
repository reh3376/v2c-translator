# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Download the free, no-key datasets for the wider research effort.

Usage:  uv run scripts/fetch_public_data.py [--out data/raw]

`dd214kw build-index --download` fetches everything the CLI itself needs. This script
also pulls research/evaluation files the CLI doesn't use (VOW Act enhanced crosswalk,
Army KSA crosswalk, ESCO/CIP/RAPIDS/OOH crosswalks). Keyed sources (O*NET Web Services
v2, CareerOneStop, Lightcast, USAJOBS, ACE API) are not fetched; see
docs/data-sources.md for sign-up links.
"""

import argparse
import zipfile
from pathlib import Path

import httpx

ONET = "https://www.onetcenter.org"
SOURCES: dict[str, str] = {
    # DMDC military occupation crosswalk (MOC -> DoD occ -> SOC/O*NET), CSV/XLSX/ACCDB
    "military_crosswalk.zip": f"{ONET}/dl_files/2019/military_crosswalk.zip",
    # Supplemental MOC -> O*NET links from the service COOL sites and ASVAB CEP
    "cool_supplemental_data.xlsx": f"{ONET}/dl_files/2019/cool_supplemental_data.xlsx",
    "citm_supplemental_data.xlsx": f"{ONET}/dl_files/2019/citm_supplemental_data.xlsx",
    # Army MOS -> O*NET via KSA analysis (very broad fan-out; research use only)
    "army_ksa_crosswalk.xlsx": f"{ONET}/dl_files/2010/army_ksa_crosswalk.xlsx",
    # VOW Act enhanced crosswalk: 68 MOCs with min pay grade + attainability (eval set)
    "vow222.xls": f"{ONET}/dl_files/ncsc/vow222.xls",
    # Civilian-side crosswalks
    "ESCO_to_ONET-SOC.xlsx": f"{ONET}/crosswalks/esco/ESCO_to_ONET-SOC.xlsx",
    "Education_CIP_to_ONET_SOC.xlsx": f"{ONET}/crosswalks/cip/Education_CIP_to_ONET_SOC.xlsx",
    "Apprenticeship_RAPIDS_to_ONET-SOC.xlsx": (
        f"{ONET}/crosswalks/rapids/Apprenticeship_RAPIDS_to_ONET-SOC.xlsx"
    ),
    "Occupation_Handbook_to_ONET-SOC.xlsx": (
        f"{ONET}/crosswalks/ooh/Occupation_Handbook_to_ONET-SOC.xlsx"
    ),
    # Full O*NET database (tasks, skills, titles, software, etc.), tab-delimited
    "db_31_0_text.zip": f"{ONET}/dl_files/database/db_31_0_text.zip",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("data/raw"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with httpx.Client(follow_redirects=True, timeout=120) as client:
        for name, url in SOURCES.items():
            dest = args.out / name
            r = client.get(url)
            r.raise_for_status()
            dest.write_bytes(r.content)
            print(f"{name:45s} {len(r.content):>12,d} bytes")
            if dest.suffix == ".zip":
                with zipfile.ZipFile(dest) as z:
                    z.extractall(args.out / dest.stem)


if __name__ == "__main__":
    main()
