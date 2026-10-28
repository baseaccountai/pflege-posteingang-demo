"""F10-AC1, AC6: after loading the seed (no network) every seed document has its chunks,
embedded with mistral-embed, and counts as indexed. If the chunker or the seed text changes,
this fails until `make seed-chunks` has been run again (needs the Mistral key)."""

import psycopg
import pytest

from app.rag.chunker import split_pages
from samples.generate import SEED_DOCUMENTS
from tests.rls.conftest import ADMIN_DSN
from tests.rls.test_seed import seed  # noqa: F401 - fixture: empty tables + supabase/seed

pytestmark = pytest.mark.db


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN) as conn:
        return conn.execute(sql, params).fetchall()


def test_seed_documents_are_indexed_with_precomputed_chunks(seed):  # noqa: F811
    for doc in SEED_DOCUMENTS:
        rows = admin(
            "select content, embedding_model, vector_dims(embedding) from public.chunks"
            " where document_id = %s order by created_at, id",
            [doc["id"]],
        )
        expected = [c.content for c in split_pages([(1, "\n".join(doc["lines"]))])]
        assert sorted(r[0] for r in rows) == sorted(expected), doc["id"]
        assert {(r[1], r[2]) for r in rows} == {("mistral-embed", 1024)}
    statuses = admin(
        "select distinct indexing_status::text from public.documents where id = any(%s::uuid[])",
        [[d["id"] for d in SEED_DOCUMENTS]],
    )
    assert statuses == [("done",)]
