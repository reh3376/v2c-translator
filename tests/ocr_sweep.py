"""How well the layout reader survives OCR: scan the synthetic DD-214 under each condition,
read it back, and report which fields came out right, which were left out, and which were
wrong. A wrong field is a bug; a missing one is OCR noise the reader declined to guess at.

    uv run --extra ocr python tests/ocr_sweep.py --dpi 150,200 --blur 0.6,1.2 --noise 12,36

--path layer OCRs each scan into a PDF text layer with tesseract (what a scanning app does);
--path scan reads an image-only PDF through `--ocr`. Needs tesseract and pdftoppm.
"""

from __future__ import annotations

import argparse
import itertools
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import synthetic_dd214 as form

from dd214kw.extractors import read
from dd214kw.models import Duration
from dd214kw.resolve import resolve

EXPECTED = {
    "branch": "Army",
    "pay_grade": "E6",
    "net_active": Duration(12, 3, 15),
    "foreign": Duration(1, 4, 11),
    "specialties": [("35M20", 99), ("35F10", 48)],
    "awards": 7,
    "courses": ["BASIC LEADER COURSE", "ADVANCED LEADER COURSE"],
}


def fields(pdf: Path, *, ocr: bool) -> dict[str, object]:
    profile = resolve(read(pdf, ocr=ocr)[1])
    return {
        "branch": profile.context.branch,
        "pay_grade": profile.context.pay_grade,
        "net_active": profile.service_time.get("net_active"),
        "foreign": profile.service_time.get("foreign"),
        "specialties": [(o.value.title.split()[0], o.value.months) for o in profile.occupations],
        "awards": len(profile.awards) or None,
        "courses": [t.value.title for t in profile.training] or None,
    }


def main() -> int:
    floats = lambda s: [float(x) for x in s.split(",")]  # noqa: E731
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--path", choices=["layer", "scan"], default="layer")
    p.add_argument("--dpi", type=floats, default=[200])
    p.add_argument("--blur", type=floats, default=[0.6])
    p.add_argument("--noise", type=floats, default=[12])
    p.add_argument("--rotate", type=floats, default=[0.0])
    p.add_argument("--psm", type=floats, default=[11], help="tesseract page segmentation mode")
    a = p.parse_args()

    out = Path(tempfile.mkdtemp())
    text_pdf = form.write_text_pdf(out / "form.pdf")
    wrong_any = False
    for dpi, blur, noise, rotate, psm in itertools.product(a.dpi, a.blur, a.noise, a.rotate, a.psm):
        png = form.rasterize(
            text_pdf, out / "scan.png", dpi=int(dpi), blur=blur, noise=int(noise), rotate=rotate
        )
        if a.path == "layer":
            pdf = form.write_ocr_pdf(png, out / "ocr.pdf", psm=int(psm))
        else:
            import dd214kw.extract

            dd214kw.extract.TESSERACT_CONFIG = f"--psm {int(psm)}"
            pdf = form.write_image_pdf(png, out / "image.pdf", dpi=int(dpi))
        try:
            got = fields(pdf, ocr=a.path == "scan")
        except subprocess.CalledProcessError as e:
            print(f"dpi={dpi:g} blur={blur:g} noise={noise:g} rotate={rotate:g}: {e}")
            continue
        missing = [k for k, v in got.items() if v in (None, [])]
        wrong = [k for k, v in got.items() if k not in missing and v != EXPECTED[k]]
        wrong_any |= bool(wrong)
        print(
            f"dpi={dpi:g} blur={blur:g} noise={noise:g} rotate={rotate:g} psm={psm:g}: "
            f"{len(got) - len(missing) - len(wrong)}/{len(got)} right"
            + (f"  missing={','.join(missing)}" if missing else "")
            + (f"  WRONG={','.join(wrong)}" if wrong else "")
        )
    return 1 if wrong_any else 0


if __name__ == "__main__":
    raise SystemExit(main())
