"""Write a scanned, image-only DD-214 to a path, so something can be OCR'd on demand.

    uv run --extra ocr python tests/make_scan.py --out /tmp/scan.pdf --pages 5

No PDF or image is committed to this repository, which is the whole reason this exists:
the fixture is drawn at run time from `synthetic_dd214`, every value in it is invented,
and `scripts/pii_guard.py` fails the build on a committed scan.

What needs one: `deploy/smoke.sh --scan`, which measures the container's peak memory
while OCR runs, because that number is what sizes `mem_limit` in `docs/deploy.md`. Pages
are what drive it, not the file's size, so `--pages` is the knob that matters.

Needs `pdftoppm` (poppler-utils) on PATH. Reading the result back needs tesseract too,
but writing it does not.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import synthetic_dd214 as form


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, required=True, help="Where to write the scanned PDF")
    p.add_argument("--dpi", type=int, default=300, help="Scan resolution")
    p.add_argument("--pages", type=int, default=1, help="How many times to repeat the page")
    p.add_argument("--blur", type=float, default=0.6)
    p.add_argument("--noise", type=int, default=12)
    a = p.parse_args()

    work = Path(tempfile.mkdtemp())
    png = form.rasterize(
        form.write_text_pdf(work / "form.pdf"),
        work / "scan.png",
        dpi=a.dpi,
        blur=a.blur,
        noise=a.noise,
    )
    one = form.write_image_pdf(png, work / "one.pdf", dpi=a.dpi)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.pages == 1:
        a.out.write_bytes(one.read_bytes())
    else:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(one)
        writer = PdfWriter()
        for _ in range(a.pages):
            writer.add_page(reader.pages[0])
        with a.out.open("wb") as handle:
            writer.write(handle)

    print(f"{a.out}  {a.out.stat().st_size:,d} bytes  {a.pages} page(s) at {a.dpi} dpi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
