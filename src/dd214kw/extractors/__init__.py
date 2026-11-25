"""Extractors turn one document into facts. Only this package knows document layouts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..evidence import DocType, Document, Fact, SourceFactory
from ..extract import ExtractionError, load_text
from .dd214 import Dd214, Dd214Json


class Extractor(Protocol):
    doc_type: DocType

    def sniff(self, text: str) -> float: ...  # 0..1: is this my document?

    def extract(self, text: str, source: SourceFactory) -> tuple[Document, list[Fact]]: ...


EXTRACTORS: tuple[Extractor, ...] = (Dd214(), Dd214Json())


def detect(text: str) -> Extractor:
    """The extractor that best recognises `text`; an error if none is at least 0.5 sure."""
    score, best = max(((e.sniff(text), e) for e in EXTRACTORS), key=lambda p: p[0])
    if score < 0.5:
        raise ExtractionError("Unrecognised document: no extractor knows this layout.")
    return best


def read(path: Path, *, ocr: bool = False, json_input: bool = False) -> tuple[Document, list[Fact]]:
    """Read one file into the document it is and the facts it states.

    `.json` files (or any file, with `json_input`) are read as text and not OCR'd;
    `json_input` also skips detection and uses the DD-214 JSON extractor.
    """
    if json_input or path.suffix.lower() == ".json":
        text = path.read_text()
    else:
        text = load_text(path, ocr=ocr)
    extractor = Dd214Json() if json_input else detect(text)
    return extractor.extract(text, SourceFactory.for_bytes(path.read_bytes()))
