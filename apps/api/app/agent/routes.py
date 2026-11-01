"""POST /agent (F08): a task for the agent, answered with the tools it used and its proposals.

Order of the steps:
1. The nurse's token is verified (F01, current_caller) - the BFF sends it as for every route.
2. The task is checked for prompt injection like a question (F07-AC9), as the nurse.
3. The agent gets its own token: exchanged at Zitadel or, in the fallback, signed by the
   API (ADR 0012). It is verified like any token (AC3) and becomes the agent principal:
   the nurse's identity and wards with actor_type = 'agent'. The token stays in this
   request - not stored, not logged, not sent to the browser.
4. The loop (runner.py) runs as the agent; each model call is booked against llm_call.
5. One agent_task event closes the task (F12); without it the answer is not delivered.
"""

import logging
import uuid
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app import audit
from app.agent.runner import run_agent
from app.agent.token_exchange import AgentTokenUnavailable
from app.agent.tools import ToolContext
from app.auth.dependencies import VerifiedCaller, current_caller
from app.auth.principal import Principal
from app.auth.tokens import InvalidToken
from app.documents.routes import database, error, quota_refused
from app.privacy.gateway import PseudonymizationFailed
from app.providers.embeddings.base import EmbeddingUnavailable
from app.providers.llm.base import LlmUnavailable
from app.quotas import QuotaExceeded, consume
from app.security.request_check import check_request

log = logging.getLogger(__name__)
router = APIRouter()

NOT_FOUND = HTTPException(status_code=404, detail="Nicht gefunden")
AGENT_DOWN = "Der Agent ist gerade nicht verfügbar – bitte später erneut versuchen."
UNAVAILABLE = "Das KI-Modell ist gerade nicht erreichbar – bitte gleich erneut versuchen."
REFUSED = "Der Auftrag wurde aus Datenschutzgründen nicht gesendet."
AUDIT_DOWN = "Die Antwort kann gerade nicht protokolliert werden – bitte später erneut versuchen."

Caller = Annotated[VerifiedCaller, Depends(current_caller)]


class Task(BaseModel):
    task: str = Field(min_length=1, max_length=500)
    resident_id: str | None = None  # chosen in the app


@router.post("/agent")
async def run_task(request: Request, caller: Caller, body: Task):
    db = database(request)
    gateway = request.app.state.gateway
    tokens = request.app.state.agent_tokens
    nurse = caller.principal

    def noter(principal: Principal):
        async def note(action: str, outcome: str = "ok", **details) -> bool:
            try:
                await audit.log(db, principal, action, outcome, **details)
            except audit.AuditFailed:
                log.exception("audit event %s could not be written", action)
                return False
            return True

        return note

    async def refused(principal: Principal = nurse):
        await noter(principal)("blocked", "blocked", error_code="pseudonymization_failed")
        return error(422, "pseudonymization_failed", REFUSED)

    if tokens is None:
        return error(503, "agent_unavailable", AGENT_DOWN)

    stopped = await check_request(
        db, gateway, nurse, body.task, noter(nurse), "agent_task", refused
    )
    if stopped is not None:
        return stopped

    try:
        agent_token = await tokens.issuer.issue(caller.token, caller.claims)
        agent = tokens.verifier.verify(agent_token, nurse.sub, nurse.ward_ids)
    except (AgentTokenUnavailable, InvalidToken):
        log.exception("no agent token")  # the exception names no token (token_exchange.py)
        return error(503, "agent_unavailable", AGENT_DOWN)
    del agent_token  # used once, for the principal above

    async def book() -> None:
        async with db.as_principal(agent) as conn:
            await consume(conn, "llm_call", 1)

    async def log_step(action: str, outcome: str = "ok", **details) -> None:
        await audit.log(db, agent, action, outcome, **details)  # AuditFailed ends the task

    note = noter(agent)
    ctx = ToolContext(
        db=db,
        principal=agent,
        gateway=gateway,
        min_similarity=request.app.state.settings.rag_min_similarity,
    )
    try:
        result = await run_agent(ctx, body.task, body.resident_id, book=book, log=log_step)
    except QuotaExceeded as exceeded:
        return await quota_refused(db, agent, exceeded)
    except LlmUnavailable:
        await note("agent_task", "error", model=gateway.llm_model, error_code="llm_unavailable")
        return error(503, "llm_unavailable", UNAVAILABLE)
    except EmbeddingUnavailable:
        await note(
            "agent_task", "error", model=gateway.embedding_model, error_code="embedding_unavailable"
        )
        return error(503, "embedding_unavailable", UNAVAILABLE)
    except PseudonymizationFailed:
        return await refused(agent)
    except audit.AuditFailed:
        log.exception("audit event of an agent step could not be written")
        return error(503, "audit_unavailable", AUDIT_DOWN)

    model = gateway.llm_model if result.model_calls else None
    if not await note("agent_task", model=model):
        return error(503, "audit_unavailable", AUDIT_DOWN)
    return {
        "answer": result.answer,
        "tools_used": result.tools_used,
        "proposals": result.proposals,
        "model": gateway.llm_model,
        "stopped": result.stopped,
    }


# --- deciding a proposal (F08-AC5, AC6) ------------------------------------------------------

EXPIRED = "Der Vorschlag ist abgelaufen (15 Minuten) – bitte den Agenten erneut fragen."
DECIDED = "Über diesen Vorschlag wurde schon entschieden."
TOO_LATE = "Die Bestätigung ist zu lange her – bitte den Agenten erneut fragen."


def _proposal_id(proposal_id: str) -> str:
    """Malformed, unknown, foreign and other people's proposals: the same 404."""
    try:
        return str(uuid.UUID(proposal_id))
    except ValueError as invalid:
        raise NOT_FOUND from invalid


async def _state(conn, proposal_id: str) -> tuple[str, bool, str | None]:
    """(status, expired, follow-up id) of a proposal the caller may see (RLS), else 404."""
    cur = await conn.execute(
        "select p.status, p.expires_at <= now(),"
        " (select f.id::text from public.follow_ups f where f.proposal_id = p.id)"
        " from public.agent_proposals p where p.id = %s",
        [proposal_id],
    )
    row = await cur.fetchone()
    if row is None:
        raise NOT_FOUND
    return row


@router.post("/agent/proposals/{proposal_id}/confirm")
async def confirm_proposal(request: Request, caller: Caller, proposal_id: str):
    db = database(request)
    tokens = request.app.state.agent_tokens
    nurse = caller.principal
    proposal_id = _proposal_id(proposal_id)
    if tokens is None:
        return error(503, "agent_unavailable", AGENT_DOWN)  # before anything is decided

    # Step 1 as the human: only she can set "confirmed" (RLS: created_for, open, in time).
    async with db.as_principal(nurse) as conn:
        status, expired, follow_up = await _state(conn, proposal_id)
        if status == "open" and expired:
            return error(409, "proposal_expired", EXPIRED)
        # (Without the follow-up check the unique proposal_id would refuse it as well -
        # after a needless token exchange.)
        if status == "dismissed" or follow_up is not None:
            return error(409, "proposal_decided", DECIDED)
        if status == "open":
            cur = await conn.execute(
                "update public.agent_proposals set status = 'confirmed'"
                " where id = %s and status = 'open' returning 1",
                [proposal_id],
            )
            if await cur.fetchone() is None:  # decided or expired a moment ago
                return error(409, "proposal_decided", DECIDED)
    # Here the proposal is confirmed but has no follow-up yet - also when step 2 failed
    # earlier: confirming again only repeats it.

    # Step 2 as the agent, with a fresh agent token: RLS allows exactly this follow-up.
    try:
        agent_token = await tokens.issuer.issue(caller.token, caller.claims)
        agent = tokens.verifier.verify(agent_token, nurse.sub, nurse.ward_ids)
    except (AgentTokenUnavailable, InvalidToken):
        log.exception("no agent token")
        return error(503, "agent_unavailable", AGENT_DOWN)
    del agent_token
    try:
        async with db.as_principal(agent) as conn:
            cur = await conn.execute(
                "insert into public.follow_ups (ward_id, resident_id, title, due_date, proposal_id)"
                " select ward_id, resident_id, title, due_date, id"
                " from public.agent_proposals where id = %s returning id::text",
                [proposal_id],
            )
            (follow_up,) = await cur.fetchone()
    except psycopg.errors.UniqueViolation:
        return error(409, "proposal_decided", DECIDED)  # a parallel request was faster
    except psycopg.errors.InsufficientPrivilege:
        return error(409, "confirmation_too_old", TOO_LATE)  # RLS: within 2 minutes only
    return {"follow_up_id": follow_up}


@router.post("/agent/proposals/{proposal_id}/dismiss")
async def dismiss_proposal(request: Request, caller: Caller, proposal_id: str):
    db = database(request)
    proposal_id = _proposal_id(proposal_id)
    async with db.as_principal(caller.principal) as conn:
        status, expired, _ = await _state(conn, proposal_id)
        if status == "open" and expired:
            return error(409, "proposal_expired", EXPIRED)
        cur = await conn.execute(
            "update public.agent_proposals set status = 'dismissed'"
            " where id = %s and status = 'open' returning 1",
            [proposal_id],
        )
        if await cur.fetchone() is None:
            return error(409, "proposal_decided", DECIDED)
    return {"ok": True}
