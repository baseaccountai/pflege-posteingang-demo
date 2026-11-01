"""Index every approved document again with the configured embedding model (F05-AC13, F11-AC19).

    make reindex      (LLM_PROVIDER etc. from the environment; `make up-local` calls it)

Why: vectors of different models cannot be compared. The seed brings chunks computed with
mistral-embed; in the fully local mode the API embeds with Ollama (bge-m3), so the seed
documents must be indexed again before questions find them. Chunks of other models are
never searched together anyway (app.match_chunks filters by model) - this makes them usable.

Local database only: the shell's SUPABASE_DB_ADMIN_URL and DATABASE_URL are ignored on
purpose, so the public demo keeps its mistral-embed chunks.

How: the admin connection only marks the approved documents "pending" again; the indexing
itself is the normal Indexer, acting as a PDL principal (both wards) - RLS and the chunk
policies apply as for every approval.
"""

import asyncio
import sys

import psycopg

from app.auth.principal import Principal
from app.config import Settings
from app.db import Database
from app.privacy.gateway import ModelGateway, create_gateway
from app.rag.indexer import Indexer
from scripts.local_db_roles import LOCAL_PASSWORDS
from scripts.reset_demo import LOCAL_ADMIN_DSN

LOCAL_GATEWAY_DSN = (
    f"postgresql://api_gateway:{LOCAL_PASSWORDS['api_gateway']}@127.0.0.1:56322/postgres"
)
# Who indexes: like a PDL, the only role that sees both wards. Named in the audit log.
REINDEXER = Principal(
    sub="reindex", app_role="pdl", ward_ids=("wb1", "wb2"), display_name="Neuindizierung"
)


def connection_strings() -> tuple[str, str]:
    """(admin, gateway) of the local Supabase - never taken from the environment."""
    return LOCAL_ADMIN_DSN, LOCAL_GATEWAY_DSN


async def reindex(db: Database, gateway: ModelGateway, admin_dsn: str) -> tuple[int, int]:
    """Returns (indexed, failed)."""
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        rows = conn.execute(
            "update public.documents set indexing_status = 'pending'"
            " where status = 'approved' returning id::text"
        ).fetchall()
    indexer = Indexer(db, gateway)
    for (document_id,) in rows:
        await indexer.run(REINDEXER, document_id)  # a failure marks the document "failed"
    with psycopg.connect(admin_dsn) as conn:
        (failed,) = conn.execute(
            "select count(*) from public.documents"
            " where id = any(%s) and indexing_status = 'failed'",
            [[doc for (doc,) in rows]],
        ).fetchone()
    return len(rows) - failed, failed


async def main() -> None:
    admin_dsn, gateway_dsn = connection_strings()
    db = Database(gateway_dsn)
    await db.open()
    try:
        gateway = create_gateway(Settings(), db)
        print(f"Neu indizieren mit {gateway.embedding_model} …")
        indexed, failed = await reindex(db, gateway, admin_dsn)
    finally:
        await db.close()
    print(f"{indexed} Dokumente indiziert, {failed} fehlgeschlagen.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
