"""F10-AC14: the committed sample record (apps/web/src/content/sample-record.json) and its
documents (apps/web/public/muster/) are exactly what the seed gives - read like the API
reads it, as a WB1 nurse under RLS. If the seed changes, run `make sample-record`."""

import json
from datetime import date

import pytest

from scripts.build_sample_record import (
    PUBLIC_DIR,
    SAMPLE_RECORD,
    berlin_today,
    read_record,
    shift_days,
    to_static,
)
from tests.rls.test_seed import seed  # noqa: F401 - fixture: empty tables + supabase/seed

pytestmark = [pytest.mark.db, pytest.mark.anyio]


async def test_the_committed_sample_record_matches_the_seed(seed: None, db) -> None:  # noqa: F811
    committed = json.loads(SAMPLE_RECORD.read_text(encoding="utf-8"))
    record, _ = await read_record(db)

    # The seed's times are relative to the day it runs; move the file to today first.
    days = (berlin_today() - date.fromisoformat(committed["generated_on"])).days
    assert shift_days(committed["record"], days) == to_static(record)


async def test_the_sample_documents_are_the_seed_files(seed: None, db) -> None:  # noqa: F811
    record, files = await read_record(db)
    assert record["documents"], "the sample resident has documents"
    for document in record["documents"]:
        published = PUBLIC_DIR / f"{document['id']}.pdf"
        assert published.read_bytes() == files[document["id"]]


def test_the_sample_record_is_a_seeded_resident_with_medication_and_origin() -> None:
    record = json.loads(SAMPLE_RECORD.read_text(encoding="utf-8"))["record"]
    assert record["resident"]["display_name"] == "Fr. Beispiel"
    assert record["medications"]["active"]
    assert all(m["provenance"]["document_id"] for m in record["medications"]["active"])
