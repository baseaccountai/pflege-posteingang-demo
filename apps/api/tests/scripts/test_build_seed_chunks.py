"""F10-AC1, AC6: the seed brings precomputed chunks with embeddings, so the nightly reset
needs no LLM or embedding call. The SQL is rendered from the seed documents and the chunker."""

import pytest

from app.providers.embeddings.fake import FakeEmbeddings
from app.rag.chunker import split_pages
from samples.generate import SEED_DOCUMENTS
from scripts.build_seed_chunks import render_sql, seed_chunks

pytestmark = pytest.mark.anyio


def test_every_seed_document_gets_chunks_with_its_metadata():
    rows = seed_chunks()
    by_doc = {doc["id"]: doc for doc in SEED_DOCUMENTS}
    assert {row["document_id"] for row in rows} == set(by_doc)
    for row in rows:
        doc = by_doc[row["document_id"]]
        assert (row["doc_type"], row["document_date"]) == (doc["doc_type"], doc["date"])
        assert row["ward_id"] in ("wb1", "wb2") and row["resident_id"]
        assert row["page"] == 1


def test_the_chunks_are_what_the_chunker_makes_of_the_seed_text():
    first = SEED_DOCUMENTS[0]
    expected = [c.content for c in split_pages([(1, "\n".join(first["lines"]))])]
    assert [r["content"] for r in seed_chunks() if r["document_id"] == first["id"]] == expected


async def test_the_sql_inserts_every_chunk_with_vector_and_marks_the_documents_indexed():
    rows = seed_chunks()
    vectors = await FakeEmbeddings().embed([r["content"] for r in rows])
    sql = render_sql(rows, vectors, "mistral-embed")
    assert sql.count("insert into public.chunks") == len(rows)
    assert sql.count("::extensions.vector") == len(rows)
    assert "'mistral-embed'" in sql
    for doc in SEED_DOCUMENTS:
        assert doc["id"] in sql.split("update public.documents set indexing_status = 'done'")[1]
    # Text with quotes cannot break the SQL (dollar quoting).
    tricky = [dict(rows[0], content="O'Neil $x$ ;--")]
    assert "$chunk$O'Neil $x$ ;--$chunk$" in render_sql(tricky, vectors[:1], "mistral-embed")


async def test_the_sql_refuses_vectors_of_the_wrong_size():
    rows = seed_chunks()[:1]
    with pytest.raises(ValueError):
        render_sql(rows, [[0.1] * 3], "mistral-embed")
