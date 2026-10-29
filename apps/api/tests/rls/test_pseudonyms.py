"""F06-AC3, F06-AC8: every resident has a stable code; the name directory is backend-only."""

import re

import psycopg
import pytest

from app.auth.principal import Principal
from app.privacy.gateway import database_directory, database_visible
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT, WB2_RESIDENT

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
AGENT_WB1 = Principal(
    sub="u-wb1",
    app_role="nurse",
    ward_ids=("wb1",),
    display_name="Pflegekraft WB1",
    actor_type="agent",
)


def test_every_resident_gets_a_unique_code_without_meaning(seeded: None) -> None:
    with psycopg.connect(ADMIN_DSN) as conn:
        codes = [row[0] for row in conn.execute("select pseudonym from public.residents")]
    assert len(codes) == 2 and len(set(codes)) == 2
    assert all(re.fullmatch(r"[A-Z]\d{2}", code) for code in codes)


async def test_the_backend_role_reads_names_and_birth_dates_of_all_wards(db) -> None:
    async with db.connection() as conn:
        cur = await conn.execute("select * from app.pseudonym_directory()")
        columns = [c.name for c in cur.description]
        rows = await cur.fetchall()
    assert columns == ["resident_id", "pseudonym", "display_name", "birth_date"]
    assert {str(row[0]) for row in rows} == {WB1_RESIDENT, WB2_RESIDENT}


@pytest.mark.parametrize("principal", [NURSE_WB1, AGENT_WB1], ids=["nurse", "agent"])
async def test_no_caller_role_may_read_the_directory(db, principal) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(principal) as conn:
            await conn.execute("select * from app.pseudonym_directory()")


def test_anon_may_not_read_the_directory(seeded: None) -> None:
    with psycopg.connect(ADMIN_DSN) as conn:
        conn.execute("set role anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("select * from app.pseudonym_directory()")


def test_the_backend_role_may_call_no_other_app_function(seeded: None) -> None:
    # usage on schema app is needed for the directory; it must not open anything else.
    with psycopg.connect(ADMIN_DSN) as conn:
        callable_functions = [
            row[0]
            for row in conn.execute(
                "select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace"
                " where n.nspname = 'app'"
                " and has_function_privilege('api_gateway', p.oid, 'execute')"
            )
        ]
    assert callable_functions == ["pseudonym_directory"]


async def test_the_gateway_loads_all_residents_but_restores_only_visible_ones(db) -> None:
    directory = await database_directory(db)()
    assert {r.resident_id for r in directory} == {WB1_RESIDENT, WB2_RESIDENT}
    assert await database_visible(db)(NURSE_WB1) == {WB1_RESIDENT}
