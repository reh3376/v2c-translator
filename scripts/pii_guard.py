"""Fail when a file looks like, or contains, a real service record.

    python scripts/pii_guard.py [PATH ...]

With no paths, scans every file that `git ls-files` lists. Prints `path:line: reason`
for each finding and exits 1 if there is any. Findings never echo the matched value,
so CI logs don't republish it.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# Scanned or photographed records. Tests that need a PDF render one at runtime.
RECORD_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".gif", ".bmp"}

ID_PATTERNS = (
    (re.compile(rb"\b\d{3}-\d{2}-\d{4}\b"), "SSN-shaped value"),
    (re.compile(rb"\b\d{9,10}\b"), "SSN- or DoD ID-shaped number"),
)

# Synthetic values that fixtures and tests may use.
PLACEHOLDERS = {
    b"000-00-0000",
    b"123-45-6789",
    b"000000000",
    b"0000000000",
    b"123456789",
    b"1234567890",
}


def findings(path: Path):
    suffix = path.suffix.lower()
    if suffix in RECORD_SUFFIXES:
        yield 0, f"{suffix} file: records and scans must not be committed"
        return
    if not path.is_file():
        return
    for lineno, line in enumerate(path.read_bytes().splitlines(), 1):
        for pattern, reason in ID_PATTERNS:
            for match in pattern.finditer(line):
                if match[0] not in PLACEHOLDERS:
                    yield lineno, reason


def main(argv: list[str]) -> int:
    if not argv:
        listed = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True)
        argv = [os.fsdecode(p) for p in listed.stdout.split(b"\0") if p]
    found = False
    for arg in argv:
        for lineno, reason in findings(Path(arg)):
            print(f"{arg}:{lineno}: {reason}")
            found = True
    if found:
        print(
            "pii_guard: remove the record or value. A synthetic placeholder belongs in "
            "PLACEHOLDERS in scripts/pii_guard.py.",
            file=sys.stderr,
        )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
