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
from typing import Annotated

from fastapi import APIRouter, Depends, Request
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
        agent = tokens.verifier.verify(agent_token, nurse.sub)
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
