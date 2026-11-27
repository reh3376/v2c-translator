"""Write a scanned DD-214 to a path, so something can be OCR'd on demand.

    uv run --extra ocr python tests/make_scan.py --out /tmp/scan.pdf --pages 5
    uv run --extra ocr python tests/make_scan.py --out /tmp/rescan.pdf --kind text-layer

No PDF or image is committed to this repository, which is the whole reason this exists:
the fixture is drawn at run time from `synthetic_dd214`, every value in it is invented,
and `scripts/pii_guard.py` fails the build on a committed scan.

Two kinds, because the hosted container reads a scan two different ways and both have
broken there:

- `image` has no text layer, so the whole page goes through OCR. `deploy/smoke.sh --scan`
  measures the container's peak memory on one of these, because that number is what sizes
  `mem_limit` in `docs/deploy.md`. Pages drive it, not the file's size, so `--pages` is
  the knob that matters.
- `text-layer` is what a plain office scanner writes: the page as an image with one
  reading of it over the top, and that reading garbles block 12. Every value in that block
  then has to be cut out of the image and read again, which is the path that needs a
  writable temporary directory. `deploy/smoke.sh --block12` asserts the whole of block 12
  comes back from one of these, inside the read-only container.

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
    p.add_argument(
        "--kind",
        choices=["image", "text-layer"],
        default="image",
        help="image: no text layer, the whole page is OCR'd. text-layer: a scanner's own "
        "PDF, whose reading of block 12 is garbled, so every cell is re-read from the image.",
    )
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
    if a.kind == "image":
        one = form.write_image_pdf(png, work / "one.pdf", dpi=a.dpi)
    else:
        one = form.write_scan_pdf(
            png, work / "one.pdf", cells=form.DRIFTED_CELLS, cell_drift=form.CELL_DRIFT
        )

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

    print(f"{a.out}  {a.out.stat().st_size:,d} bytes  {a.pages} page(s) at {a.dpi} dpi, {a.kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
