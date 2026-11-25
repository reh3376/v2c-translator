"""DD-215 extractor: a correction to one DD-214, as pre-extracted JSON fields.

There is no text reader yet. DoDI 1336.01 leaves the wording of a correction to each
service, so a text reader waits on a real sample.
"""

from __future__ import annotations

import json

from ..evidence import DocType, Document, Fact, SourceFactory
from ..extract import ExtractionError
from .dd214 import _json_date, _json_facts, _json_form, _json_object

# DD-214 keys a DD-215 can carry but this reader does not apply. resolve() keeps the latest
# ServiceContext whole, so a partial one would blank every field the correction leaves out.
CONTEXT_KEYS = ("branch", "component", "grade", "pay_grade")


class Dd215Json:
    """A DD-215 as a JSON object.

    Keys: form ("DD-215"), corrects_separation_date (required: the separation date of the
    DD-214 it corrects), issued (optional). Duration keys (net_active, prior_active,
    foreign_service, sea_service) give the corrected value. List keys (specialty,
    decorations, education) add entries. Dates are YYYY-MM-DD or YYYYMMDD.
    """

    doc_type: DocType = "dd215"

    def sniff(self, text: str) -> float:
        data = _json_object(text)
        return 1.0 if data is not None and _json_form(data) == "DD215" else 0.0

    def extract(self, text: str, source: SourceFactory) -> tuple[Document, list[Fact]]:
        data = json.loads(text)
        period_end = _json_date(data, "corrects_separation_date")
        if period_end is None:
            raise ExtractionError(
                "A DD-215 needs corrects_separation_date: the separation date of the DD-214 "
                "it corrects."
            )
        issued = _json_date(data, "issued")
        facts = _json_facts(data, lambda key: source(self.doc_type, key, issued), period_end)
        ignored = [k for k in CONTEXT_KEYS if data.get(k)]
        notes = (f"DD-215 corrections to {', '.join(ignored)} are not applied.",) if ignored else ()
        return Document(self.doc_type, source.doc_id, "json", notes), facts
