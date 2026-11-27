"""Golden output: each fixture renders byte-identical to its report in docs/examples/.

Guards refactors that must not change behaviour. If a change is meant to alter output,
regenerate docs/examples/ in the same commit (see README, Development).
"""

import json
from pathlib import Path

import pytest

from dd214kw.cli import main
from dd214kw.index import DEFAULT_INDEX

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ["army_2000.txt", "navy_2022.txt", "airforce.json", "marines.json"]

pytestmark = pytest.mark.skipif(not DEFAULT_INDEX.exists(), reason="index not built")


@pytest.mark.parametrize("fixture", FIXTURES)
def test_example_report_unchanged(fixture, tmp_path):
    out = tmp_path / "report.md"
    src = ROOT / "tests" / "fixtures" / fixture
    assert main(["translate", str(src), "-f", "md", "-o", str(out)]) == 0
    expected = ROOT / "docs" / "examples" / f"{Path(fixture).stem}.md"
    assert out.read_text(encoding="utf-8") == expected.read_text(encoding="utf-8")


@pytest.mark.parametrize("fixture", FIXTURES)
def test_both_formats_from_one_run_match_the_two_separate_runs(fixture, tmp_path):
    """`-f json+md` prints what `-f json` and `-f md` print, and reads the files once.

    The web server runs one translation per upload because of this, so if the envelope
    ever drifted from either format the page would show something the CLI does not.
    """
    src = ROOT / "tests" / "fixtures" / fixture
    out = {}
    for fmt in ("json", "md", "json+md"):
        out[fmt] = tmp_path / f"report.{fmt}"
        assert main(["translate", str(src), "-f", fmt, "-o", str(out[fmt])]) == 0

    bundle = json.loads(out["json+md"].read_text(encoding="utf-8"))

    assert bundle["markdown"] == out["md"].read_text(encoding="utf-8")
    assert bundle["report"] == json.loads(out["json"].read_text(encoding="utf-8"))
