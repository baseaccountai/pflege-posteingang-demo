"""F10-AC10: daily and per-session quotas are enforced atomically by the database."""

import asyncio
import hashlib

import psycopg
import pytest

from app.auth.principal import Principal
from app.quotas import QuotaExceeded, consume
from tests.rls.conftest import ADMIN_DSN

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE = Principal(sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1")
SESSION = hashlib.sha256(b"session-1").hexdigest()


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


@pytest.fixture(autouse=True)
def clean_counters():
    admin("truncate public.usage_counters")
    limits = admin("select kind, max_count from public.quota_limits")
    yield
    for kind, max_count in limits:  # tests lower limits; put the migration values back
        admin("update public.quota_limits set max_count = %s where kind = %s", [max_count, kind])
    admin("truncate public.usage_counters")


def set_limit(kind: str, max_count: int) -> None:
    admin("update public.quota_limits set max_count = %s where kind = %s", [max_count, kind])


async def book(db, kind: str, amount: int, subject: str = "global") -> bool:
    async with db.as_principal(NURSE) as conn:
        cur = await conn.execute("select app.consume_quota(%s, %s, %s)", [kind, subject, amount])
        return (await cur.fetchone())[0]


def test_limits_from_the_migration():
    assert dict(admin("select kind || '/' || scope, max_count from public.quota_limits")) == {
        "upload/session": 5,
        "ocr_page/global": 100,
        "llm_call/global": 300,
        "embed_chunk/global": 500,
    }


async def test_bookings_succeed_up_to_the_limit_and_then_fail(db):
    set_limit("ocr_page", 3)
    assert [await book(db, "ocr_page", 1) for _ in range(4)] == [True, True, True, False]
    assert admin("select count from public.usage_counters") == [(3,)]


async def test_a_first_booking_above_the_limit_and_a_zero_limit_fail(db):
    set_limit("ocr_page", 3)
    assert await book(db, "ocr_page", 4) is False
    set_limit("llm_call", 0)
    assert await book(db, "llm_call", 1) is False
    assert admin("select count(*) from public.usage_counters") == [(0,)]


@pytest.mark.parametrize("amount", [0, -1, 21])
async def test_only_amounts_from_1_to_20_are_accepted(db, amount):
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await book(db, "ocr_page", amount)


async def test_an_unknown_kind_is_rejected(db):
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await book(db, "free_lunch", 1)


async def test_parallel_bookings_never_exceed_the_limit(db):
    set_limit("llm_call", 10)
    results = await asyncio.gather(*(book(db, "llm_call", 1) for _ in range(30)))
    assert results.count(True) == 10
    assert admin("select count from public.usage_counters") == [(10,)]


async def test_global_quotas_ignore_the_subject_so_it_cannot_be_dodged(db):
    set_limit("ocr_page", 2)
    assert await book(db, "ocr_page", 2, subject="anything") is True
    assert await book(db, "ocr_page", 1, subject="something-else") is False
    assert admin("select subject from public.usage_counters") == [("global",)]


async def test_daily_quotas_count_per_berlin_day_and_session_quotas_for_the_whole_session(db):
    assert await book(db, "ocr_page", 1)
    assert await book(db, "upload", 1, subject=SESSION)
    rows = dict(admin("select kind, period from public.usage_counters"))
    today = admin("select ((now() at time zone 'Europe/Berlin')::date)::text")[0][0]
    assert rows == {"ocr_page": today, "upload": "lifetime"}  # not reset at midnight


async def test_session_quotas_need_a_session_hash(db):
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await book(db, "upload", 1, subject="global")


async def test_six_uploads_in_one_session_fail_another_session_still_works(db):
    other = hashlib.sha256(b"session-2").hexdigest()
    assert [await book(db, "upload", 1, SESSION) for _ in range(6)][-2:] == [True, False]
    assert await book(db, "upload", 1, other) is True


@pytest.mark.parametrize(
    "sql",
    [
        "update public.quota_limits set max_count = 1000000",
        "insert into public.usage_counters values ('lifetime', 'upload', 'x', -100)",
        "update public.usage_counters set count = 0",
        "delete from public.usage_counters",
    ],
)
async def test_callers_cannot_change_limits_or_counters(db, sql):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(NURSE) as conn:
            await conn.execute(sql)


def test_anon_cannot_book():
    with psycopg.connect(ADMIN_DSN) as conn:
        conn.execute("set local role anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("select app.consume_quota('ocr_page', 'global', 1)")


async def test_consume_raises_quota_exceeded_and_rolls_back_earlier_bookings(db):
    # The upload books several quotas in one transaction: all or nothing.
    set_limit("llm_call", 0)
    with pytest.raises(QuotaExceeded) as error:
        async with db.as_principal(NURSE) as conn:
            await consume(conn, "ocr_page", 2)
            await consume(conn, "llm_call", 1)
    assert error.value.kind == "llm_call"
    assert admin("select count(*) from public.usage_counters") == [(0,)]
