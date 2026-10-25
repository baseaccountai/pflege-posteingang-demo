"""Fixtures for tests against the local Supabase database (`supabase start`).

The admin connection only prepares data; every assertion runs through the
`api_gateway` login role, exactly like the API does in production.
"""

import os
from collections.abc import AsyncIterator, Iterator

import psycopg
import pytest

from app.db import Database

ADMIN_DSN = os.environ.get(
    "TEST_ADMIN_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:56322/postgres"
)
# Local-only password, set by the fixture below; never used outside tests.
GATEWAY_PASSWORD = "api_gateway_local_test"
# TEST_DATABASE_URL points the same tests at the cloud database (spike F01); then the
# real api_gateway password is used and the fixture must not overwrite it.
CLOUD_DSN = os.environ.get("TEST_DATABASE_URL")
GATEWAY_DSN = CLOUD_DSN or f"postgresql://api_gateway:{GATEWAY_PASSWORD}@127.0.0.1:56322/postgres"

WB1_RESIDENT = "11111111-1111-1111-1111-111111111111"
WB2_RESIDENT = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def seeded() -> Iterator[None]:
    """Two wards with one resident each, inserted with admin rights."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        if not CLOUD_DSN:
            conn.execute(f"alter role api_gateway password '{GATEWAY_PASSWORD}'")
        conn.execute("truncate public.residents, public.wards cascade")
        conn.execute("insert into public.wards (id, name) values ('wb1', 'WB 1'), ('wb2', 'WB 2')")
        conn.execute(
            "insert into public.residents (id, ward_id, display_name)"
            " values (%s, 'wb1', 'Hr. Muster-Bauer'), (%s, 'wb2', 'Fr. Testfeld')",
            [WB1_RESIDENT, WB2_RESIDENT],
        )
    yield


@pytest.fixture
async def db(seeded: None) -> AsyncIterator[Database]:
    database = Database(GATEWAY_DSN, max_size=4)
    await database.open()
    try:
        yield database
    finally:
        await database.close()
