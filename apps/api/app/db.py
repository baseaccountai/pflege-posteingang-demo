"""Database access on behalf of a user.

The API logs in as the low-privilege role `api_gateway`. For every request it opens a
transaction, switches to the role `authenticated` and stores the caller's claims in
`request.jwt.claims`. Row Level Security policies read these claims, so the database
itself guarantees that a nurse only sees rows of her own ward.

Both settings are `local`: they end with the transaction, also on rollback, so a pooled
connection never carries the claims of a previous caller.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from app.auth.principal import Principal


class Database:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10) -> None:
        self._pool = AsyncConnectionPool(
            dsn,
            min_size=min_size,
            max_size=max_size,
            open=False,
            # Supabase's transaction pooler does not support prepared statements.
            kwargs={"prepare_threshold": None},
        )

    async def open(self) -> None:
        await self._pool.open(wait=True)

    async def close(self) -> None:
        await self._pool.close()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection]:
        """Raw connection as `api_gateway` (no table rights) – for health checks and tests."""
        async with self._pool.connection() as conn:
            yield conn

    async def in_maintenance(self) -> bool:
        """True while the nightly reset runs (F10-AC7); read through app.in_maintenance()."""
        async with self._pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("set local role authenticated")
                cur = await conn.execute("select app.in_maintenance()")
                (flag,) = await cur.fetchone()
                return bool(flag)

    @asynccontextmanager
    async def as_principal(self, principal: Principal) -> AsyncIterator[AsyncConnection]:
        """One transaction in which RLS applies with the principal's claims."""
        async with self._pool.connection() as conn:
            async with conn.transaction():
                await conn.execute("set local role authenticated")
                await conn.execute(
                    "select set_config('request.jwt.claims', %s, true)",
                    [json.dumps(principal.as_claims())],
                )
                yield conn
