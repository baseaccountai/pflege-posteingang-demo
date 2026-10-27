"""F03-AC8, F03-AC9: the resident record (medications, events, diagnoses, follow-ups)
stays in its ward, references cannot cross wards, nothing is deleted, and finished
documents are frozen - enforced by the database."""

import uuid

import psycopg
import pytest

from app.auth.principal import Principal
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT, WB2_RESIDENT

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
NURSE_WB2 = Principal(
    sub="u-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2"
)
PDL = Principal(sub="u-pdl", app_role="pdl", ward_ids=("wb1", "wb2"), display_name="PDL")
RECORD_TABLES = ["medications", "medication_events", "diagnoses", "follow_ups"]


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def admin_document(ward: str, status: str = "ready_for_review") -> str:
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, uploaded_by, upload_session, status)"
        " values (%s, %s, 'u-admin', 'sid', %s)",
        [doc, ward, status],
    )
    return doc


@pytest.fixture
def record(seeded) -> dict:
    """One entry of every kind per ward, written with admin rights."""
    ids = {}
    for ward, resident in [("wb1", WB1_RESIDENT), ("wb2", WB2_RESIDENT)]:
        doc = admin_document(ward, "approved")
        (med,) = admin(
            "insert into public.medications (ward_id, resident_id, name, strength, dosage,"
            " created_by) values (%s, %s, 'Ramipril', '5 mg', '{\"morgens\": \"1\"}', 'u-admin')"
            " returning id::text",
            [ward, resident],
        )[0]
        admin(
            "insert into public.medication_events (ward_id, medication_id, kind, document_id,"
            " after, actor_type, created_by, confirmed_by, confirmed_by_name)"
            " values (%s, %s, 'new', %s, '{}', 'human', 'u-admin', 'u-admin', 'Admin')",
            [ward, med, doc],
        )
        admin(
            "insert into public.diagnoses (ward_id, resident_id, text, source_document_id,"
            " actor_type, created_by, confirmed_by, confirmed_by_name)"
            " values (%s, %s, 'Hypertonie', %s, 'human', 'u-admin', 'u-admin', 'Admin')",
            [ward, resident, doc],
        )
        (follow_up,) = admin(
            "insert into public.follow_ups (ward_id, resident_id, title, due_date,"
            " source_document_id, actor_type, created_by, confirmed_by, confirmed_by_name)"
            " values (%s, %s, 'Kontrolle', current_date, %s, 'human', 'u-admin', 'u-admin',"
            " 'Admin') returning id::text",
            [ward, resident, doc],
        )[0]
        ids[ward] = {"doc": doc, "med": med, "follow_up": follow_up}
    return ids


async def run(principal: Principal, db, sql: str, params: list | None = None) -> list[tuple]:
    async with db.as_principal(principal) as conn:
        cur = await conn.execute(sql, params)
        return await cur.fetchall() if cur.description else []


@pytest.mark.parametrize("table", RECORD_TABLES)
async def test_wb2_sees_only_wb2_entries_without_filter(db, record, table):
    assert await run(NURSE_WB2, db, f"select distinct ward_id from public.{table}") == [("wb2",)]


async def test_wb2_cannot_write_into_wb1(db, record):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await run(
            NURSE_WB2,
            db,
            "insert into public.diagnoses (ward_id, resident_id, text) values ('wb1', %s, 'x')",
            [WB1_RESIDENT],
        )


async def test_an_entry_cannot_point_to_a_resident_of_another_ward(db, record):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        await run(
            NURSE_WB2,
            db,
            "insert into public.medications (ward_id, resident_id, name, dosage)"
            " values ('wb2', %s, 'X', '{}')",
            [WB1_RESIDENT],
        )


async def test_an_entry_cannot_cite_a_document_of_another_ward(db, record):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        await run(
            NURSE_WB2,
            db,
            "insert into public.diagnoses (ward_id, resident_id, text, source_document_id)"
            " values ('wb2', %s, 'x', %s)",
            [WB2_RESIDENT, record["wb1"]["doc"]],
        )


async def test_an_event_cannot_belong_to_a_medication_of_another_ward(db, record):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        await run(
            NURSE_WB2,
            db,
            "insert into public.medication_events (ward_id, medication_id, kind, after)"
            " values ('wb2', %s, 'changed', '{}')",
            [record["wb1"]["med"]],
        )


@pytest.mark.parametrize("table", RECORD_TABLES)
async def test_nothing_in_the_record_can_be_deleted(db, record, table):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await run(NURSE_WB2, db, f"delete from public.{table}")


@pytest.mark.parametrize(
    "sql",
    [
        "update public.medication_events set kind = 'new'",
        "update public.diagnoses set text = 'erfunden'",
        "update public.medications set name = 'Anderes Mittel'",
        "update public.follow_ups set title = 'Anderer Titel'",
    ],
)
async def test_history_and_facts_cannot_be_rewritten(db, record, sql):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await run(NURSE_WB2, db, sql)


async def test_a_medication_may_change_dose_and_status_but_not_its_resident(db, record):
    med = record["wb2"]["med"]
    await run(
        NURSE_WB2,
        db,
        "update public.medications set strength = '10 mg', status = 'discontinued' where id = %s",
        [med],
    )
    other = str(uuid.uuid4())
    admin(
        "insert into public.residents (id, ward_id, display_name)"
        " values (%s, 'wb2', 'Hr. Exempel')",
        [other],
    )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await run(NURSE_WB2, db, "update public.medications set resident_id = %s", [other])


async def test_a_follow_up_can_be_marked_done(db, record):
    await run(
        NURSE_WB2,
        db,
        "update public.follow_ups set status = 'done', done_by = 'u-wb2',"
        " done_by_name = 'Pflegekraft WB2', done_at = now() where id = %s",
        [record["wb2"]["follow_up"]],
    )
    assert admin(
        "select status from public.follow_ups where id = %s", [record["wb2"]["follow_up"]]
    ) == [("done",)]


async def test_who_confirmed_comes_from_the_claims(db, record):
    rows = await run(
        NURSE_WB2,
        db,
        "insert into public.diagnoses (ward_id, resident_id, text) values ('wb2', %s, 'x')"
        " returning created_by, confirmed_by, confirmed_by_name, actor_type",
        [WB2_RESIDENT],
    )
    assert rows == [("u-wb2", "u-wb2", "Pflegekraft WB2", "human")]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await run(
            NURSE_WB2,
            db,
            "insert into public.diagnoses (ward_id, resident_id, text, confirmed_by_name)"
            " values ('wb2', %s, 'x', 'Chefarzt')",
            [WB2_RESIDENT],
        )


@pytest.mark.parametrize("status", ["approved", "rejected"])
@pytest.mark.parametrize(
    "change",
    [
        "status = 'ready_for_review'",
        "doc_type = 'sonstiges'",
        "document_date = '2020-01-01'",
        "suggestion = '{}'",
        "ocr_pages = '[]'",
        "approved_by_name = 'Jemand'",
    ],
)
async def test_finished_documents_are_frozen(db, seeded, status, change):
    doc = admin_document("wb2", status)
    with pytest.raises(psycopg.errors.CheckViolation):
        await run(NURSE_WB2, db, f"update public.documents set {change} where id = %s", [doc])


async def test_the_indexing_status_of_an_approved_document_stays_changeable(db, seeded):
    doc = admin_document("wb2", "approved")
    await run(
        NURSE_WB2, db, "update public.documents set indexing_status = 'done' where id = %s", [doc]
    )
    assert admin("select indexing_status::text from public.documents where id = %s", [doc]) == [
        ("done",)
    ]


async def test_a_document_in_review_can_still_be_finished(db, seeded):
    doc = admin_document("wb2", "ready_for_review")
    await run(
        NURSE_WB2,
        db,
        "update public.documents set status = 'approved', resident_id = %s where id = %s",
        [WB2_RESIDENT, doc],
    )


async def test_done_by_must_be_the_caller(db, record):
    # F04-AC8: "erledigt von" comes from the claims, like "freigegeben von" (F03).
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await run(
            NURSE_WB2,
            db,
            "update public.follow_ups set status = 'done', done_by = 'someone-else',"
            " done_by_name = 'Pflegekraft WB2', done_at = now() where id = %s",
            [record["wb2"]["follow_up"]],
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await run(
            NURSE_WB2,
            db,
            "update public.follow_ups set status = 'done', done_by = 'u-wb2',"
            " done_by_name = 'PDL', done_at = now() where id = %s",
            [record["wb2"]["follow_up"]],
        )


async def test_a_done_follow_up_cannot_be_reopened_or_rewritten(db, record):
    follow_up = record["wb2"]["follow_up"]
    admin(
        "update public.follow_ups set status = 'done', done_by = 'u-x', done_by_name = 'X',"
        " done_at = now() where id = %s",
        [follow_up],
    )
    await run(
        NURSE_WB2, db, "update public.follow_ups set status = 'open' where id = %s", [follow_up]
    )
    assert admin("select status, done_by from public.follow_ups where id = %s", [follow_up]) == [
        ("done", "u-x")
    ]
