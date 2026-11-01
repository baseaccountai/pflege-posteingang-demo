"""F11-AC19, F05-AC13: `make reindex` indexes every approved document with the configured
embedding model - after it, no chunk of another model is left (they are never searched
together anyway). Documents not approved are not touched. Runs through the Indexer as a
PDL principal (both wards), so RLS and the chunk policies apply as for every indexing."""

import json
import uuid

import psycopg
import pytest

from app.config import Settings
from app.privacy.gateway import create_gateway
from app.providers.embeddings.fake import FakeEmbeddings
from scripts.reindex import reindex
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT, WB2_RESIDENT
from tests.rls.test_chunks_rls import add_chunk, unit

pytestmark = [pytest.mark.db, pytest.mark.anyio]

PAGES = [{"page": 1, "markdown": "# Arztbrief\n## Medikation\nRamipril 5 mg morgens."}]


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def document(ward: str, resident: str, status: str = "approved") -> str:
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, resident_id, uploaded_by, upload_session,"
        " status, doc_type, document_date, screened_pages, indexing_status)"
        " values (%s, %s, %s, 'u', 's', %s, 'arztbrief', '2026-10-20', %s, 'done')",
        [doc, ward, resident, status, json.dumps(PAGES)],
    )
    return doc


def chunk_models(doc: str) -> list[str]:
    return [
        m
        for (m,) in admin("select embedding_model from public.chunks where document_id = %s", [doc])
    ]


async def test_every_approved_document_gets_chunks_of_the_configured_model_only(seeded, db):
    admin("truncate public.usage_counters")
    wb1, wb2 = document("wb1", WB1_RESIDENT), document("wb2", WB2_RESIDENT)
    in_review = document("wb1", WB1_RESIDENT, status="ready_for_review")
    add_chunk(wb1, "wb1", WB1_RESIDENT, unit(0), model="mistral-embed")  # as the seed has it
    gateway = create_gateway(Settings(llm_provider="fake"), db, embeddings=FakeEmbeddings())

    assert await reindex(db, gateway, ADMIN_DSN) == (2, 0)

    for doc in (wb1, wb2):
        models = chunk_models(doc)
        assert models and set(models) == {FakeEmbeddings.model_name}
    assert chunk_models(in_review) == []
    assert admin("select indexing_status::text from public.documents where id = %s", [wb1]) == [
        ("done",)
    ]
    admin("truncate public.usage_counters")


async def test_a_document_that_fails_is_counted_and_stays_failed(seeded, db):
    admin("truncate public.usage_counters")
    doc = document("wb1", WB1_RESIDENT)

    class Down(FakeEmbeddings):
        async def embed(self, texts):
            from app.providers.embeddings.base import EmbeddingUnavailable

            raise EmbeddingUnavailable("Ollama läuft nicht")

    gateway = create_gateway(Settings(llm_provider="fake"), db, embeddings=Down())
    assert await reindex(db, gateway, ADMIN_DSN) == (0, 1)
    assert admin("select indexing_status::text from public.documents where id = %s", [doc]) == [
        ("failed",)
    ]
