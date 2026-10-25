"""F01-AC9, F01-AC10, F01-AC11: ward isolation is enforced by the database (RLS)."""

import asyncio

import psycopg
import pytest

from app.auth.principal import Principal

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
NURSE_WB2 = Principal(
    sub="u-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2"
)
PDL = Principal(sub="u-pdl", app_role="pdl", ward_ids=("wb1", "wb2"), display_name="PDL")


async def ward_ids_seen(db, principal) -> set[str]:
    async with db.as_principal(principal) as conn:
        cur = await conn.execute("select ward_id from public.residents")  # deliberately no filter
        return {row[0] for row in await cur.fetchall()}


async def test_wb2_sees_no_wb1_rows_without_filter(db):
    assert await ward_ids_seen(db, NURSE_WB2) == {"wb2"}


async def test_wb1_sees_only_wb1(db):
    assert await ward_ids_seen(db, NURSE_WB1) == {"wb1"}


async def test_pdl_sees_both_wards(db):
    assert await ward_ids_seen(db, PDL) == {"wb1", "wb2"}


async def test_claims_do_not_survive_a_rolled_back_transaction(db):
    with pytest.raises(psycopg.errors.DivisionByZero):
        async with db.as_principal(NURSE_WB1) as conn:
            await conn.execute("select 1/0")
    # Next transaction (pool max size reuses connections) must only see WB2.
    assert await ward_ids_seen(db, NURSE_WB2) == {"wb2"}
    async with db.connection() as conn:
        cur = await conn.execute(
            "select current_user, coalesce(current_setting('request.jwt.claims', true), '')"
        )
        assert await cur.fetchone() == ("api_gateway", "")


async def test_parallel_requests_of_both_wards_stay_isolated(db):
    principals = [NURSE_WB1 if i % 2 else NURSE_WB2 for i in range(20)]
    results = await asyncio.gather(*(ward_ids_seen(db, p) for p in principals))
    for principal, seen in zip(principals, results, strict=True):
        assert seen == set(principal.ward_ids)


async def test_without_claims_nothing_is_visible_and_writes_fail(db):
    async with db.connection() as conn:
        async with conn.transaction():
            await conn.execute("set local role authenticated")
            cur = await conn.execute("select count(*) from public.residents")
            assert (await cur.fetchone())[0] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.connection() as conn:
            async with conn.transaction():
                await conn.execute("set local role authenticated")
                await conn.execute(
                    "insert into public.residents (ward_id, display_name) values ('wb1', 'x')"
                )


async def test_nurse_cannot_insert_residents(db):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(
                "insert into public.residents (ward_id, display_name) values ('wb2', 'x')"
            )


async def test_gateway_role_itself_has_no_table_access(db):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.connection() as conn:
            await conn.execute("select * from public.residents")


async def test_anon_has_no_access(db):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.connection() as conn:
            async with conn.transaction():
                await conn.execute("set local role anon")
                await conn.execute("select * from public.residents")
