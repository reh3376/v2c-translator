"""scripts/pii_guard.py, run the way CI and pre-commit run it."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

# Built at runtime so this file passes the guard itself.
SSN = "123-55-" + "6789"
BARE_SSN = SSN.replace("-", "")
DOD_ID = "12345" + "09876"


def guard(*paths, cwd=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pii_guard.py"), *map(str, paths)],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def test_flags_ssn_without_printing_it(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text(f"SAMPLE JORDAN\nSSN {SSN}\n")
    r = guard(f)
    assert r.returncode == 1
    assert r.stdout.splitlines() == [f"{f}:2: SSN-shaped value"]
    assert SSN not in r.stdout + r.stderr


def test_flags_undashed_ssn_and_dod_id(tmp_path):
    f = tmp_path / "record.json"
    f.write_text(f'{{"ssn": "{BARE_SSN}",\n "dod_id": "{DOD_ID}"}}\n')
    r = guard(f)
    assert r.returncode == 1
    assert [line.split(": ")[0] for line in r.stdout.splitlines()] == [f"{f}:1", f"{f}:2"]


def test_flags_record_files_by_extension(tmp_path):
    pdf, photo = tmp_path / "dd214.pdf", tmp_path / "IMG_0001.JPG"
    pdf.write_bytes(b"%PDF-1.7\n")
    photo.write_bytes(b"\xff\xd8\xff")
    r = guard(pdf, photo)
    assert r.returncode == 1
    assert [line.split(":")[0] for line in r.stdout.splitlines()] == [str(pdf), str(photo)]


def test_passes_placeholders_and_synthetic_fixtures(tmp_path):
    f = tmp_path / "army.txt"
    f.write_text("SAMPLE, JORDAN E-6\nSSN 000-00-0000 DOD ID 0000000000 DOB 19900101\n")
    r = guard(f, *sorted(FIXTURES.iterdir()))
    assert (r.returncode, r.stdout) == (0, "")


def test_without_paths_scans_tracked_files_only(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "dd214.pdf").write_bytes(b"%PDF-1.7\n")
    (tmp_path / "untracked.txt").write_text(f"SSN {SSN}\n")
    subprocess.run(["git", "add", "dd214.pdf"], cwd=tmp_path, check=True)
    r = guard(cwd=tmp_path)
    assert r.returncode == 1
    assert [line.split(":")[0] for line in r.stdout.splitlines()] == ["dd214.pdf"]
