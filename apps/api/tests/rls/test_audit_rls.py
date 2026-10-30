"""F12-AC2 to AC6, AC8, AC9: the audit log in the database itself.

State changes are written by triggers in the same transaction as the change; model,
question and block events only through app.log_event with a fixed list of actions. The
actor always comes from the claims of the session, never from a parameter. Only the PDL
reads the log, nobody changes or deletes an event.
"""

import uuid

import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.auth.principal import Principal
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT, WB2_RESIDENT

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
PDL = Principal(sub="u-pdl", app_role="pdl", ward_ids=("wb1", "wb2"), display_name="PDL")
AGENT_WB1 = Principal(
    sub="u-wb1",
    app_role="nurse",
    ward_ids=("wb1",),
    display_name="Pflegekraft WB1",
    actor_type="agent",
)
UPLOAD = "insert into public.documents (id, ward_id, upload_session) values (%s, 'wb1', 's')"
EVENT_COLUMNS = (
    "action, outcome, actor_type, actor_sub, actor_name, on_behalf_of_name, ward_id,"
    " model, document_id::text, resident_id::text, details"
)


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def events(document_id: str) -> list[tuple]:
    return admin(
        f"select {EVENT_COLUMNS} from public.audit_events where document_id = %s order by id",
        [document_id],
    )


def document(ward: str = "wb1", status: str = "ready_for_review") -> str:
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, uploaded_by, upload_session, status,"
        " screening_result, screened_pages, suggestion_model)"
        " values (%s, %s, 'u-wb1', 's', %s, 'clean', '[]', 'mistral-small-latest')",
        [doc, ward, status],
    )
    return doc


async def log_event(db, principal, action, outcome="ok", model=None, doc=None, resident=None, **d):
    async with db.as_principal(principal) as conn:
        await conn.execute(
            "select app.log_event(%s, %s, %s, %s, %s, %s)",
            [action, outcome, model, doc, resident, Jsonb(d)],
        )


async def test_an_upload_is_logged_with_the_actor_from_the_claims(db):
    doc = str(uuid.uuid4())
    async with db.as_principal(NURSE_WB1) as conn:
        await conn.execute(
            UPLOAD,
            [doc],
        )
    assert events(doc) == [
        ("upload", "ok", "human", "u-wb1", "Pflegekraft WB1", None, "wb1", None, doc, None, {})
    ]


async def test_no_change_without_its_event_and_no_event_without_its_change(db):
    doc = str(uuid.uuid4())
    with pytest.raises(psycopg.errors.CheckViolation):
        async with db.as_principal(NURSE_WB1) as conn:
            await conn.execute(
                UPLOAD,
                [doc],
            )
            await conn.execute(
                "update public.documents set status = 'approved' where id = %s", [doc]
            )  # not a step of the state machine: the whole transaction is rolled back
    assert events(doc) == []


async def test_status_changes_approval_and_rejection_are_logged(db):
    approved, rejected, failed = document(), document(), document(status="extracting")
    async with db.as_principal(NURSE_WB1) as conn:
        await conn.execute(
            "update public.documents set status = 'approved', resident_id = %s where id = %s",
            [WB1_RESIDENT, approved],
        )
        await conn.execute(
            "update public.documents set status = 'rejected' where id = %s", [rejected]
        )
        await conn.execute(
            "update public.documents set status = 'failed', error_code = 'llm_unavailable'"
            " where id = %s",
            [failed],
        )
    (approval,) = events(approved)
    assert approval[:3] == ("approval", "ok", "human") and approval[9] == WB1_RESIDENT
    assert [e[:2] for e in events(rejected)] == [("rejection", "ok")]
    assert [(e[0], e[1], e[10]) for e in events(failed)] == [
        ("status_change", "error", {"status": "failed", "error_code": "llm_unavailable"})
    ]


async def test_a_ready_suggestion_names_its_model(db):
    doc = document(status="extracting")
    async with db.as_principal(NURSE_WB1) as conn:
        await conn.execute(
            "update public.documents set status = 'ready_for_review' where id = %s", [doc]
        )
    assert [(e[0], e[7], e[10]) for e in events(doc)] == [
        ("status_change", "mistral-small-latest", {"status": "ready_for_review"})
    ]


async def test_record_entries_are_logged(db):
    doc = document()
    async with db.as_principal(NURSE_WB1) as conn:
        await conn.execute(
            "insert into public.diagnoses (ward_id, resident_id, text, source_document_id)"
            " values ('wb1', %s, 'Hypertonie', %s)",
            [WB1_RESIDENT, doc],
        )
        await conn.execute(
            "insert into public.follow_ups (ward_id, resident_id, title, source_document_id)"
            " values ('wb1', %s, 'Blutdruck kontrollieren', %s)",
            [WB1_RESIDENT, doc],
        )
    logged = [(e[0], e[9], e[10]) for e in events(doc)]
    assert logged == [
        ("record_entry", WB1_RESIDENT, {"entry": "diagnosis"}),
        ("record_entry", WB1_RESIDENT, {"entry": "follow_up"}),
    ]
    # F12-AC3: the diagnosis text itself is not in the log.
    assert "Hypertonie" not in str(events(doc))


async def test_admin_work_without_claims_is_not_logged(db):
    # Seed, reset and test setup run without a user; there is nobody to name.
    assert events(document()) == []


async def test_log_event_takes_the_actor_from_the_claims(db):
    doc = document()
    await log_event(db, NURSE_WB1, "screening", "blocked", "ministral-8b-latest", doc, rule_id="x")
    await log_event(db, AGENT_WB1, "agent_tool", doc=doc, tool="read_record")
    assert [(e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[10]) for e in events(doc)] == [
        ("screening", "blocked", "human", "u-wb1", "Pflegekraft WB1", None, "wb1",
         "ministral-8b-latest", {"rule_id": "x"}),
        ("agent_tool", "ok", "agent", "u-wb1", "KI-Agent", "Pflegekraft WB1", "wb1",
         None, {"tool": "read_record"}),
    ]  # fmt: skip


@pytest.mark.parametrize(
    "action", ["upload", "status_change", "approval", "rejection", "record_entry", "x"]
)
async def test_log_event_refuses_state_changes_and_unknown_actions(db, action):
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await log_event(db, NURSE_WB1, action)


@pytest.mark.parametrize(
    "details",
    [
        {"question": "Wie ist Ramipril dosiert?"},  # F12-AC3: no texts
        {"rule_id": "x" * 101},
        {"rule_id": {"nested": "Hr. Muster-Bauer"}},
    ],
)
async def test_log_event_refuses_details_that_could_carry_content(db, details):
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await log_event(db, NURSE_WB1, "question", **details)


async def test_log_event_refuses_an_unknown_outcome(db):
    with pytest.raises(psycopg.errors.InvalidParameterValue):
        await log_event(db, NURSE_WB1, "question", outcome="fine")


async def test_log_event_cannot_point_into_another_ward(db):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await log_event(db, NURSE_WB1, "question", doc=document("wb2"))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await log_event(db, NURSE_WB1, "question", resident=WB2_RESIDENT)


async def test_the_ward_is_the_callers_or_none_for_several(db):
    marker = str(uuid.uuid4())[:8]
    await log_event(db, NURSE_WB1, "question", error_code=marker)
    await log_event(db, PDL, "question", error_code=marker)
    wards = admin(
        "select ward_id from public.audit_events where details ->> 'error_code' = %s order by id",
        [marker],
    )
    assert wards == [("wb1",), (None,)]


async def test_only_the_pdl_reads_the_log(db):
    doc = document()
    await log_event(db, NURSE_WB1, "question", doc=doc)
    async with db.as_principal(NURSE_WB1) as conn:
        cur = await conn.execute("select count(*) from public.audit_events")
        assert (await cur.fetchone())[0] == 0
    async with db.as_principal(PDL) as conn:
        cur = await conn.execute(
            "select count(*) from public.audit_events where document_id = %s", [doc]
        )
        assert (await cur.fetchone())[0] == 1


@pytest.mark.parametrize(
    "statement",
    [
        "insert into public.audit_events (action, outcome, actor_type, actor_sub, actor_name)"
        " values ('question', 'ok', 'human', 'u-wb2', 'Jemand anderes')",
        "update public.audit_events set outcome = 'ok'",
        "delete from public.audit_events",
    ],
)
async def test_nobody_writes_the_table_directly(db, statement):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(PDL) as conn:
            await conn.execute(statement)


def test_not_even_the_admin_changes_or_deletes_an_event(seeded):
    doc = document()
    admin(
        "insert into public.audit_events (action, outcome, actor_type, actor_sub, actor_name,"
        " document_id) values ('question', 'ok', 'human', 'u-wb1', 'Pflegekraft WB1', %s)",
        [doc],
    )
    for statement in (
        "update public.audit_events set outcome = 'blocked' where document_id = %s",
        "delete from public.audit_events where document_id = %s",
    ):
        with pytest.raises(psycopg.errors.RaiseException):
            admin(statement, [doc])
    assert len(events(doc)) == 1
