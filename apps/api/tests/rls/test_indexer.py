"""F05-AC1, AC1a: after the approval the document's OCR pages become chunks with metadata,
replaced atomically on a new run; a failure leaves indexing_status = failed and the old
chunks in place (the approval stays valid). Runs as the user, under RLS."""

import asyncio
import uuid

import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.auth.principal import Principal
from app.providers.embeddings.base import EmbeddingUnavailable
from app.providers.embeddings.fake import FakeEmbeddings
from app.rag.indexer import Indexer
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT
from tests.support.gateway import db_gateway

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
NURSE_WB2 = Principal(
    sub="u-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2"
)
PAGES = [
    {
        "page": 1,
        "markdown": "# Arztbrief\nKlinikum Musterstadt\n\n## Diagnosen\n- Herzinsuffizienz",
    },
    {"page": 2, "markdown": "## Procedere\nKontrolle beim Hausarzt in zwei Wochen."},
]


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def document(status: str = "approved", pages=PAGES, indexing: str | None = "pending") -> str:
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, resident_id, uploaded_by, upload_session,"
        " status, doc_type, document_date, ocr_pages, indexing_status)"
        " values (%s, 'wb1', %s, 'u', 's', %s, 'arztbrief', '2026-10-20', %s, %s)",
        [doc, WB1_RESIDENT, status, Jsonb(pages), indexing],
    )
    return doc


def chunk_rows(doc: str) -> list[tuple]:
    return admin(
        "select page, heading, resident_id::text, doc_type::text, document_date::text,"
        " embedding_model from public.chunks where document_id = %s order by page, heading",
        [doc],
    )


def indexing_status(doc: str) -> str:
    return admin("select indexing_status::text from public.documents where id = %s", [doc])[0][0]


class FailingEmbeddings(FakeEmbeddings):
    async def embed(self, texts):
        self.calls.append(list(texts))
        raise EmbeddingUnavailable("down")


@pytest.fixture
def quotas():
    admin("truncate public.usage_counters")
    yield
    admin("update public.quota_limits set max_count = 500 where kind = 'embed_chunk'")
    admin("truncate public.usage_counters")


async def test_an_approved_document_becomes_chunks_with_page_and_metadata(db, seeded, quotas):
    doc = document()
    await Indexer(db, db_gateway(db, embeddings=FakeEmbeddings())).run(NURSE_WB1, doc)
    assert chunk_rows(doc) == [
        (1, "Arztbrief", WB1_RESIDENT, "arztbrief", "2026-10-20", "fake-embed (Testattrappe)"),
        (1, "Diagnosen", WB1_RESIDENT, "arztbrief", "2026-10-20", "fake-embed (Testattrappe)"),
        (2, "Procedere", WB1_RESIDENT, "arztbrief", "2026-10-20", "fake-embed (Testattrappe)"),
    ]
    assert indexing_status(doc) == "done"
    assert admin("select count from public.usage_counters where kind = 'embed_chunk'") == [(3,)]


async def test_indexing_again_replaces_the_chunks(db, seeded, quotas):
    doc = document()
    await Indexer(db, db_gateway(db, embeddings=FakeEmbeddings())).run(NURSE_WB1, doc)
    admin("update public.documents set indexing_status = 'failed' where id = %s", [doc])
    await Indexer(db, db_gateway(db, embeddings=FakeEmbeddings())).run(NURSE_WB1, doc)
    assert len(chunk_rows(doc)) == 3


async def test_two_runs_at_the_same_time_do_not_duplicate_chunks(db, seeded, quotas):
    doc = document()
    await asyncio.gather(
        Indexer(db, db_gateway(db, embeddings=FakeEmbeddings())).run(NURSE_WB1, doc),
        Indexer(db, db_gateway(db, embeddings=FakeEmbeddings())).run(NURSE_WB1, doc),
    )
    assert len(chunk_rows(doc)) == 3


async def test_an_embedding_failure_marks_failed_and_keeps_the_old_chunks(db, seeded, quotas):
    doc = document()
    await Indexer(db, db_gateway(db, embeddings=FakeEmbeddings())).run(NURSE_WB1, doc)
    admin("update public.documents set indexing_status = 'pending' where id = %s", [doc])
    await Indexer(db, db_gateway(db, embeddings=FailingEmbeddings())).run(NURSE_WB1, doc)
    assert indexing_status(doc) == "failed"
    assert len(chunk_rows(doc)) == 3
    assert admin("select status::text from public.documents where id = %s", [doc]) == [
        ("approved",)
    ]


async def test_a_used_up_quota_marks_failed_without_calling_the_model(db, seeded, quotas):
    admin("update public.quota_limits set max_count = 0 where kind = 'embed_chunk'")
    doc, embeddings = document(), FakeEmbeddings()
    await Indexer(db, db_gateway(db, embeddings=embeddings)).run(NURSE_WB1, doc)
    assert indexing_status(doc) == "failed"
    assert embeddings.calls == [] and chunk_rows(doc) == []


async def test_a_long_document_books_its_chunks_in_steps(db, seeded, quotas):
    # app.consume_quota accepts 1 to 20 per booking; 25 sections are booked in two steps.
    pages = [{"page": 1, "markdown": "\n".join(f"## Abschnitt {i}\nText {i}" for i in range(25))}]
    doc = document(pages=pages)
    await Indexer(db, db_gateway(db, embeddings=FakeEmbeddings())).run(NURSE_WB1, doc)
    assert len(chunk_rows(doc)) == 25
    assert admin("select count from public.usage_counters where kind = 'embed_chunk'") == [(25,)]


@pytest.mark.parametrize(
    ("principal", "status", "indexing"),
    [
        (NURSE_WB2, "approved", "pending"),  # foreign ward: the document does not exist for her
        (NURSE_WB1, "ready_for_review", None),  # not approved yet
        (NURSE_WB1, "approved", "done"),  # already indexed
    ],
    ids=["foreign-ward", "not-approved", "already-done"],
)
async def test_nothing_happens_for_documents_that_are_not_due(
    db, seeded, quotas, principal, status, indexing
):
    doc, embeddings = document(status=status, indexing=indexing), FakeEmbeddings()
    await Indexer(db, db_gateway(db, embeddings=embeddings)).run(principal, doc)
    assert embeddings.calls == [] and chunk_rows(doc) == []
    if indexing:
        assert indexing_status(doc) == indexing  # unchanged


async def test_the_embedding_model_sees_no_resident_name(db, seeded, quotas):
    # F06-AC1, AC4: the vectors come from pseudonymised text; the stored chunk keeps the
    # original (it is pseudonymised again before every model call).
    pages = [{"page": 1, "markdown": "## Medikation\nHr. Muster-Bauer bekommt Ramipril 5 mg."}]
    embeddings = FakeEmbeddings()
    doc = document(pages=pages)
    await Indexer(db, db_gateway(db, embeddings=embeddings)).run(NURSE_WB1, doc)
    sent = " ".join(text for call in embeddings.calls for text in call)
    assert "Muster-Bauer" not in sent and "Bewohner_" in sent
    stored = admin("select content from public.chunks where document_id = %s", [doc])
    assert "Hr. Muster-Bauer" in stored[0][0]
