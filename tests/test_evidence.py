"""Fact kinds, provenance, extraction and the privacy guarantee."""

import dataclasses
import hashlib
import json
import typing
from datetime import date
from pathlib import Path

import pytest

from dd214kw.cli import main
from dd214kw.evidence import Accomplishment, Fact, SkillClaim, Source, scrub
from dd214kw.extract import ExtractionError
from dd214kw.extractors import detect, read
from dd214kw.extractors.dd214 import Dd214, Dd214Json
from dd214kw.index import DEFAULT_INDEX
from dd214kw.resolve import resolve

FIX = Path(__file__).parent / "fixtures"
ARMY_PII = ("000-00-0000", "19900101", "123 TEST ST", "HONORABLE", "KBK")
PII = {"army_2000.txt": ARMY_PII, "army_vmet.txt": ("SAMPLE", "JORDAN", "TEST")}  # VMET: name
SRC = Source("eval", "aaaaaaaaaaaa", "bullet 1", None, 1.0)


def _json(obj) -> str:
    return json.dumps(dataclasses.asdict(obj), default=str).upper()


@pytest.mark.parametrize("fixture", PII)
def test_no_fact_or_profile_serialization_contains_pii(fixture):
    _, facts = read(FIX / fixture)
    for blob in [*map(_json, facts), _json(resolve(facts))]:
        for s in PII[fixture]:
            assert s not in blob


@pytest.mark.skipif(not DEFAULT_INDEX.exists(), reason="index not built")
@pytest.mark.parametrize("fixture", PII)
def test_json_report_contains_no_pii(fixture, capsys):
    assert main(["translate", str(FIX / fixture), "-f", "json"]) == 0
    out = capsys.readouterr().out.upper()
    for s in PII[fixture]:
        assert s not in out


def test_free_text_is_scrubbed_at_construction():
    text = "SSN 000-00-0000, DOB 19900101, 123 TEST ST; HONORABLE; separation code KBK. Led 12."
    acc = Accomplishment(text, (), SRC)
    for value in (acc.text, SkillClaim(text, "skill", SRC).term, dataclasses.replace(acc).text):
        assert value.endswith("Led 12.")
        for s in ARMY_PII:
            assert s not in value.upper()


def test_scrub_keeps_ordinary_text_and_is_idempotent():
    plain = "Supervised 12 Soldiers and 38 vehicles worth $4.2M; reset the AN/SPY-1 radar"
    assert scrub(plain) == plain
    dirty = "Call 555-123-4567 or email a.b@example.mil; RE-3 code"
    assert (
        scrub(scrub(dirty))
        == scrub(dirty)
        == "Call [redacted] or email [redacted]; [redacted] code"
    )


def test_fact_kinds_are_frozen():
    kinds = typing.get_args(Fact)
    assert len(kinds) == 8
    assert all(k.__dataclass_params__.frozen for k in kinds)


def test_detect_picks_the_extractor_or_refuses():
    assert isinstance(detect((FIX / "army_2000.txt").read_text()), Dd214)
    assert isinstance(detect((FIX / "airforce.json").read_text()), Dd214Json)
    with pytest.raises(ExtractionError):
        detect("hello world")


def test_json_input_reads_text_and_still_detects_the_document():
    doc, _ = read(FIX / "army_2000.txt", json_input=True)
    assert (doc.doc_type, doc.layout) == ("dd214", "2000")


def test_dd214_sources_identify_the_file_and_block():
    path = FIX / "navy_2022.txt"
    doc, facts = read(path)
    doc_id = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    assert (doc.doc_type, doc.doc_id, doc.layout, doc.notes) == ("dd214", doc_id, "2022", ())
    assert {(f.source.doc_type, f.source.doc_id) for f in facts} == {("dd214", doc_id)}
    profile = resolve(facts)
    assert profile.context.as_of == date(2023, 2, 14)  # separation date this period
    assert profile.occupations[0].sources[0].locator == "block 12"
    assert profile.training[0].sources[0].locator == "block 15"
