"""F08-AC7, AC6, AC10: what the database lets the agent do - in RLS, not only in the prompt.

The agent acts with the nurse's identity (same sub, same wards) and actor_type = 'agent'.
It may read the record of its ward, insert a proposal, and insert a follow-up only for a
proposal a human has confirmed. Every other write is checked twice: as the nurse it works
(and is rolled back), as the agent it is refused - so no test passes because its SQL is
simply broken.
"""

import uuid

import psycopg
import pytest

from app.auth.principal import Principal
from tests.rls.conftest import WB1_RESIDENT, WB2_RESIDENT
from tests.rls.test_record_rls import admin, record, run  # noqa: F401 (fixture)

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE = Principal(sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1")
AGENT = Principal(
    sub="u-wb1",
    app_role="nurse",
    ward_ids=("wb1",),
    display_name="Pflegekraft WB1",
    actor_type="agent",
)
COLLEAGUE = Principal(
    sub="u-wb1-b", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
PDL = Principal(sub="u-pdl", app_role="pdl", ward_ids=("wb1", "wb2"), display_name="PDL")
PDL_AGENT = Principal(
    sub="u-pdl", app_role="pdl", ward_ids=("wb1", "wb2"), display_name="PDL", actor_type="agent"
)
VECTOR = "array_fill(0.1::real, array[1024])::extensions.vector"
FILE = (
    "insert into public.document_files (document_id, ward_id, mime, size_bytes, content)"
    " values (%s, 'wb1', 'application/pdf', 1, 'x')"
)
FINDING = (
    "insert into public.injection_findings (document_id, ward_id, page, layer, rule_id,"
    " category, excerpt, explanation) values (%s, 'wb1', 1, 'pattern', 'r', 'c', 'e', 'x')"
)


class Rollback(Exception):
    pass


async def rows_written(principal: Principal, db, sql: str, params: list | None = None) -> int:
    """Rows the statement wrote (then rolled back); -1 if the database refused it."""
    written = 0
    try:
        async with db.as_principal(principal) as conn:
            cur = await conn.execute(sql, params)
            written = cur.rowcount
            raise Rollback
    except Rollback:
        return written
    except psycopg.errors.InsufficientPrivilege:
        return -1


@pytest.fixture
def ward(record) -> dict:  # noqa: F811
    """The record fixture plus an approved document of the resident with one chunk."""
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, resident_id, uploaded_by, upload_session,"
        " status, doc_type, document_date) values (%s, 'wb1', %s, 'u-admin', 'sid', 'approved',"
        " 'arztbrief', '2026-10-01')",
        [doc, WB1_RESIDENT],
    )
    (chunk,) = admin(
        "insert into public.chunks (document_id, ward_id, resident_id, doc_type, document_date,"
        f" page, content, embedding, embedding_model) values (%s, 'wb1', %s, 'arztbrief',"
        f" '2026-10-01', 1, 'Ramipril 5 mg', {VECTOR}, 'm') returning id::text",
        [doc, WB1_RESIDENT],
    )[0]
    uploaded = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, uploaded_by, upload_session, status)"
        " values (%s, 'wb1', 'u-admin', 'sid', 'uploaded')",
        [uploaded],
    )
    return {**record["wb1"], "approved": doc, "chunk": chunk, "uploaded": uploaded}


# --- reading ------------------------------------------------------------------------------

READABLE = ["residents", "documents", "chunks", "medications", "medication_events",
            "diagnoses", "follow_ups"]  # fmt: skip


@pytest.mark.parametrize("table", READABLE)
async def test_the_agent_reads_the_record_of_its_ward_and_nothing_of_another(db, ward, table):
    own = await run(AGENT, db, f"select ward_id from public.{table} where ward_id = 'wb1'")
    other = await run(AGENT, db, f"select ward_id from public.{table} where ward_id = 'wb2'")
    assert own and not other


async def test_a_resident_of_another_ward_does_not_exist_for_the_agent(db, ward):
    found = await run(AGENT, db, "select 1 from public.residents where id = %s", [WB2_RESIDENT])
    assert found == []


@pytest.mark.parametrize("table", ["document_files", "injection_findings", "audit_events"])
async def test_files_findings_and_the_audit_log_stay_closed_to_the_agent(db, ward, table):
    # One row each, visible to the human PDL - but not to the PDL's agent.
    admin(FILE, [ward["uploaded"]])
    admin(FINDING, [ward["uploaded"]])
    admin("insert into public.audit_events (action, outcome, actor_type, actor_sub, actor_name)"
          " values ('upload', 'ok', 'human', 'u-admin', 'Admin')")  # fmt: skip
    assert await run(PDL, db, f"select 1 from public.{table}")
    assert await run(PDL_AGENT, db, f"select 1 from public.{table}") == []


# --- every write but the two allowed ones is refused ---------------------------------------

WRITES = {
    "insert medication": (
        "insert into public.medications (ward_id, resident_id, name) values ('wb1', %s, 'X')",
        lambda w: [WB1_RESIDENT],
    ),
    "change medication": (
        "update public.medications set dosage = '{}' where id = %s",
        lambda w: [w["med"]],
    ),
    "insert medication event": (
        "insert into public.medication_events (ward_id, medication_id, kind, after)"
        " values ('wb1', %s, 'changed', '{}')",
        lambda w: [w["med"]],
    ),
    "insert diagnosis": (
        "insert into public.diagnoses (ward_id, resident_id, text) values ('wb1', %s, 'X')",
        lambda w: [WB1_RESIDENT],
    ),
    "insert follow-up without proposal": (
        "insert into public.follow_ups (ward_id, resident_id, title) values ('wb1', %s, 'X')",
        lambda w: [WB1_RESIDENT],
    ),
    "mark follow-up done": (
        "update public.follow_ups set status = 'done', done_by = app.uid(),"
        " done_by_name = app.display_name(), done_at = now() where id = %s",
        lambda w: [w["follow_up"]],
    ),
    "upload document": (
        "insert into public.documents (ward_id, uploaded_by, upload_session)"
        " values ('wb1', app.uid(), 'sid')",
        lambda w: [],
    ),
    "change document": (
        "update public.documents set attempts = attempts + 1 where id = %s",
        lambda w: [w["uploaded"]],
    ),
    "store file": (FILE, lambda w: [w["uploaded"]]),
    "insert chunk": (
        "insert into public.chunks (document_id, ward_id, resident_id, doc_type, document_date,"
        f" page, content, embedding, embedding_model) values (%s, 'wb1', %s, 'arztbrief',"
        f" '2026-10-01', 2, 'x', {VECTOR}, 'm')",
        lambda w: [w["approved"], WB1_RESIDENT],
    ),
    "delete chunk": ("delete from public.chunks where id = %s", lambda w: [w["chunk"]]),
    "insert finding": (FINDING, lambda w: [w["uploaded"]]),
}


@pytest.mark.parametrize("name", WRITES)
async def test_the_nurse_may_but_the_agent_may_not(db, ward, name):
    sql, params = WRITES[name]
    assert await rows_written(NURSE, db, sql, params(ward)) == 1, "statement itself is broken"
    assert await rows_written(AGENT, db, sql, params(ward)) <= 0


# --- proposals: the agent proposes, the human decides --------------------------------------

PROPOSE = (
    "insert into public.agent_proposals (ward_id, resident_id, title, due_date)"
    " values ('wb1', %s, 'Dosis mit Hausarzt klären', current_date + 3) returning id::text"
)


async def propose(principal: Principal = AGENT, db=None) -> str:
    (proposal,) = (await run(principal, db, PROPOSE, [WB1_RESIDENT]))[0]
    return proposal


async def decide(principal: Principal, db, proposal: str, status: str = "confirmed") -> int:
    rows = await run(
        principal,
        db,
        "update public.agent_proposals set status = %s where id = %s returning 1",
        [status, proposal],
    )
    return len(rows)


async def test_the_agent_proposes_for_its_nurse_open_for_fifteen_minutes(db, ward):
    proposal = await propose(db=db)
    ((status, created_for, minutes),) = admin(
        "select status, created_for, round(extract(epoch from expires_at - created_at) / 60)"
        " from public.agent_proposals where id = %s",
        [proposal],
    )
    assert (status, created_for, minutes) == ("open", "u-wb1", 15)


@pytest.mark.parametrize(
    "sql",
    [
        # status, recipient and expiry are not the agent's to choose
        "insert into public.agent_proposals (ward_id, resident_id, title, status)"
        " values ('wb1', %s, 'X', 'confirmed')",
        "insert into public.agent_proposals (ward_id, resident_id, title, created_for)"
        " values ('wb1', %s, 'X', 'u-other')",
        "insert into public.agent_proposals (ward_id, resident_id, title, expires_at)"
        " values ('wb1', %s, 'X', now() + interval '1 day')",
    ],
)
async def test_the_agent_cannot_set_status_recipient_or_expiry(db, ward, sql):
    assert await rows_written(AGENT, db, sql, [WB1_RESIDENT]) == -1


async def test_no_proposal_for_another_ward_and_none_by_a_human(db, ward):
    other = PROPOSE.replace("'wb1'", "'wb2'")
    with pytest.raises(psycopg.Error):
        await run(AGENT, db, other, [WB2_RESIDENT])
    assert await rows_written(NURSE, db, PROPOSE, [WB1_RESIDENT]) == -1


async def test_the_agent_cannot_confirm_change_or_delete_a_proposal(db, ward):
    proposal = await propose(db=db)
    assert await decide(AGENT, db, proposal) == 0
    assert await rows_written(
        AGENT, db, "update public.agent_proposals set title = 'X' where id = %s", [proposal]
    ) == -1  # fmt: skip
    assert await rows_written(
        AGENT, db, "delete from public.agent_proposals where id = %s", [proposal]
    ) == -1  # fmt: skip


async def test_only_the_nurse_it_was_made_for_confirms_once_and_before_it_expires(db, ward):
    proposal = await propose(db=db)
    assert await run(COLLEAGUE, db, "select 1 from public.agent_proposals") == []
    assert await decide(COLLEAGUE, db, proposal) == 0
    assert await decide(NURSE, db, proposal) == 1
    ((decided,),) = admin(
        "select decided_at > now() - interval '1 minute' from public.agent_proposals where id = %s",
        [proposal],
    )
    assert decided  # set by the database, not by the caller
    assert await decide(NURSE, db, proposal, "dismissed") == 0  # decided once

    expired = await propose(db=db)
    admin(
        "update public.agent_proposals set expires_at = now() - interval '1 second' where id = %s",
        [expired],
    )
    assert await decide(NURSE, db, expired) == 0


async def test_a_human_can_only_confirm_or_dismiss(db, ward):
    proposal = await propose(db=db)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        await decide(NURSE, db, proposal, "open")
    assert await rows_written(
        NURSE, db, "update public.agent_proposals set title = 'X' where id = %s", [proposal]
    ) == -1  # fmt: skip


# --- the follow-up: only after a human confirmed, once ------------------------------------

FOLLOW_UP = (
    "insert into public.follow_ups (ward_id, resident_id, title, due_date, proposal_id)"
    " values ('wb1', %s, 'Dosis mit Hausarzt klären', current_date + 3, %s)"
)


async def test_after_confirmation_the_agent_writes_the_follow_up_once(db, ward):
    proposal = await propose(db=db)
    assert await rows_written(AGENT, db, FOLLOW_UP, [WB1_RESIDENT, proposal]) == -1  # open
    assert await decide(NURSE, db, proposal) == 1
    await run(AGENT, db, FOLLOW_UP, [WB1_RESIDENT, proposal])
    ((actor, created_by, confirmed_by),) = admin(
        "select actor_type, created_by, confirmed_by from public.follow_ups where proposal_id = %s",
        [proposal],
    )
    assert (actor, created_by, confirmed_by) == ("agent", "u-wb1", "u-wb1")
    with pytest.raises(psycopg.errors.UniqueViolation):
        await run(AGENT, db, FOLLOW_UP, [WB1_RESIDENT, proposal])


async def test_no_follow_up_for_a_dismissed_stale_or_different_proposal(db, ward):
    dismissed = await propose(db=db)
    await decide(NURSE, db, dismissed, "dismissed")
    assert await rows_written(AGENT, db, FOLLOW_UP, [WB1_RESIDENT, dismissed]) == -1

    stale = await propose(db=db)
    await decide(NURSE, db, stale)
    admin(
        "update public.agent_proposals set decided_at = now() - interval '3 minutes' where id = %s",
        [stale],
    )
    assert await rows_written(AGENT, db, FOLLOW_UP, [WB1_RESIDENT, stale]) == -1

    confirmed = await propose(db=db)
    await decide(NURSE, db, confirmed)
    other_title = FOLLOW_UP.replace("Dosis mit Hausarzt klären", "Medikation absetzen")
    assert await rows_written(AGENT, db, other_title, [WB1_RESIDENT, confirmed]) == -1
    # ... and the human cannot take the agent's place for a proposal either
    assert await rows_written(NURSE, db, FOLLOW_UP, [WB1_RESIDENT, confirmed]) == -1
    assert await rows_written(AGENT, db, FOLLOW_UP, [WB1_RESIDENT, confirmed]) == 1


# --- F12-AC4: proposal, confirmation and dismissal are logged by trigger -------------------


async def test_proposal_and_decision_are_in_the_audit_log(db, ward):
    admin("truncate public.audit_events")
    confirmed = await propose(db=db)
    await decide(NURSE, db, confirmed)
    dismissed = await propose(db=db)
    await decide(NURSE, db, dismissed, "dismissed")
    events = admin(
        "select action, actor_type, details ->> 'proposal_id' from public.audit_events"
        " where action like '%%proposal%%' order by id"
    )
    assert events == [
        ("agent_proposal", "agent", confirmed),
        ("proposal_confirmed", "human", confirmed),
        ("agent_proposal", "agent", dismissed),
        ("proposal_dismissed", "human", dismissed),
    ]
