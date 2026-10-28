"""Indexing of approved documents for questions with sources (F05-AC1, AC1a).

Started in the background after an approval (F03-AC11) and by the retry in the record.
Everything runs as the user who approved, so RLS decides which document exists and
the chunk policies check that every chunk belongs to it.

1. Read the document. Only an approved document whose indexing is pending or failed is
   indexed; anything else (foreign ward, not approved, already done) is left alone.
2. Cut the OCR pages into chunks (rag/chunker.py).
3. Book the embedding quota BEFORE the paid call (F10-AC10).
4. Embed all chunks - outside of any transaction, a model call can take seconds.
5. One transaction, one document at a time (advisory lock): delete the old chunks, insert
   the new ones, set indexing_status = 'done'. Two runs at once cannot double the chunks.

Any failure sets indexing_status = 'failed'. The old chunks stay (step 5 never started or
was rolled back), and the approval itself is not touched: the record is valid, the document
is only not searchable yet (the record offers a retry).
"""

import logging

from app.auth.principal import Principal
from app.db import Database
from app.providers.embeddings.base import EmbeddingProvider
from app.quotas import consume
from app.rag.chunker import Chunk, split_pages

log = logging.getLogger(__name__)

MAX_BOOKING = 20  # app.consume_quota accepts 1 to 20 per call


class Indexer:
    def __init__(self, db: Database, embeddings: EmbeddingProvider):
        self.db = db
        self.embeddings = embeddings

    async def run(self, principal: Principal, document_id: str) -> None:
        try:
            await self._index(principal, document_id)
        except Exception:
            # Embedding outage, used-up quota, anything: the document stays approved.
            log.exception("indexing failed for %s", document_id)
            await self._set_status(principal, document_id, "failed")

    async def _index(self, principal: Principal, document_id: str) -> None:
        async with self.db.as_principal(principal) as conn:
            cur = await conn.execute(
                "select ward_id, resident_id::text, doc_type::text, document_date, ocr_pages"
                " from public.documents where id = %s and status = 'approved'"
                " and indexing_status in ('pending', 'failed')",
                [document_id],
            )
            document = await cur.fetchone()
        if document is None:
            return  # not visible, not approved or already indexed
        ward, resident, doc_type, document_date, ocr_pages = document
        chunks = split_pages([(p["page"], p["markdown"]) for p in ocr_pages or []])

        # The quota is booked in its own transaction: once paid for, it stays booked.
        async with self.db.as_principal(principal) as conn:
            for start in range(0, len(chunks), MAX_BOOKING):
                await consume(conn, "embed_chunk", len(chunks[start : start + MAX_BOOKING]))
        vectors = await self.embeddings.embed([chunk.content for chunk in chunks])

        async with self.db.as_principal(principal) as conn:
            # One run per document at a time; the second one waits and replaces again.
            await conn.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))", [f"index:{document_id}"]
            )
            await conn.execute("delete from public.chunks where document_id = %s", [document_id])
            for chunk, vector in zip(chunks, vectors, strict=True):
                await self._insert(
                    conn, document_id, ward, resident, doc_type, document_date, chunk, vector
                )
            await conn.execute(
                "update public.documents set indexing_status = 'done' where id = %s",
                [document_id],
            )

    async def _insert(
        self,
        conn,
        document_id,
        ward,
        resident,
        doc_type,
        document_date,
        chunk: Chunk,
        vector: list[float],
    ) -> None:
        await conn.execute(
            "insert into public.chunks (document_id, ward_id, resident_id, doc_type,"
            " document_date, page, heading, content, embedding, embedding_model)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, %s::extensions.vector, %s)",
            [
                document_id,
                ward,
                resident,
                doc_type,
                document_date,
                chunk.page,
                chunk.heading,
                chunk.content,
                "[" + ",".join(map(str, vector)) + "]",
                self.embeddings.model_name,
            ],
        )

    async def _set_status(self, principal: Principal, document_id: str, status: str) -> None:
        async with self.db.as_principal(principal) as conn:
            await conn.execute(
                "update public.documents set indexing_status = %s::public.indexing_status"
                " where id = %s and status = 'approved'",
                [status, document_id],
            )
