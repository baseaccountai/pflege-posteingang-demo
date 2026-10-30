"""POST /questions (F05): a question about the documents of the own wards, answered with
sources - or the same "no hits" for everything that cannot be found (F05-AC7).

Order of the paid steps: the question is embedded (embedding quota, in retrieve), and only
if there are hits the LLM is called (LLM quota booked first, F05-AC12, F10-AC10).
The model only sees pseudonymised text (F06, rag/answer.py).

Every question leaves one event in the audit log (F12): answered, failed, blocked or
quota exhausted - never its text. Without that event an answer is not delivered; a block
or refusal is returned either way (F12-AC8). Question events carry no resident id: a
foreign one would fail the ward check and tell it apart from "no hits" (F05-AC7).
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import audit
from app.auth.dependencies import current_principal
from app.auth.principal import Principal
from app.documents.routes import database, error, quota_refused
from app.privacy.gateway import PseudonymizationFailed
from app.providers.embeddings.base import EmbeddingUnavailable
from app.providers.llm.base import LlmUnavailable
from app.quotas import QuotaExceeded, consume
from app.rag.answer import answer_with_sources
from app.rag.retrieval import Hit, retrieve
from app.security.classifier import classify_question
from app.security.patterns import matching_rules

log = logging.getLogger(__name__)
router = APIRouter()

NO_HITS_ANSWER = "Keine Treffer in deinem Wohnbereich."
UNAVAILABLE_ANSWER = "Die Antwort ist gerade nicht möglich – bitte gleich erneut versuchen."
REFUSED_ANSWER = "Die Anfrage wurde aus Datenschutzgründen nicht gesendet."
INJECTION_MESSAGE = (
    "Die Anfrage wurde als Versuch erkannt, die Regeln der KI zu umgehen, und nicht ausgeführt."
)
# For a question only attempts to steer the AI itself count: a nurse may well ask about
# all residents of her ward (RLS keeps it there); rules on data leaks are for documents.
QUESTION_CATEGORIES = {"ignore_instructions", "role_override", "addresses_ai", "outbound_link"}
AUDIT_DOWN = "Die Antwort kann gerade nicht protokolliert werden – bitte später erneut versuchen."
SCREENING_DOWN = (
    "Die Sicherheitsprüfung ist gerade nicht verfügbar – bitte später erneut versuchen."
)

Caller = Annotated[Principal, Depends(current_principal)]


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)  # F05-AC12
    resident_id: str | None = None  # chosen in the app or linked from the record (AC5)


def _source(hit: Hit) -> dict:
    return {
        "document_id": hit.document_id,
        "doc_type": hit.doc_type,
        "document_date": hit.document_date.isoformat() if hit.document_date else None,
        "resident_name": hit.resident_name,
        "page": hit.page,
    }


@router.post("/questions")
async def ask_question(request: Request, principal: Caller, body: Question):
    db = database(request)
    gateway = request.app.state.gateway
    min_similarity = request.app.state.settings.rag_min_similarity

    def reply(
        answer: str, sources: list[Hit] | None = None, no_hits: bool = False, sent=None
    ) -> dict:
        return {
            "answer": answer,
            "sources": [_source(hit) for hit in sources or []],
            "model": gateway.llm_model,  # F05-AC10: the app names the model
            "no_hits": no_hits,
            "sent_to_model": sent,
        }

    async def note(action: str, outcome: str = "ok", **kw) -> bool:
        try:
            await audit.log(db, principal, action, outcome, **kw)
        except audit.AuditFailed:
            log.exception("audit event %s could not be written", action)
            return False
        return True

    async def refused() -> dict:
        await note("blocked", "blocked", error_code="pseudonymization_failed")  # F06-AC10
        return reply(REFUSED_ANSWER)

    async def unavailable(code: str, model: str) -> dict:
        await note("question", "error", model=model, error_code=code)
        return reply(UNAVAILABLE_ANSWER)

    async def delivered(response: dict, model: str | None) -> dict | JSONResponse:
        if not await note("question", model=model):
            return error(503, "audit_unavailable", AUDIT_DOWN)
        return response

    # F07-AC9: rules, then the checker model, see the question before any other model.
    rules = [r for r in matching_rules(body.question) if r.category in QUESTION_CATEGORIES]
    if rules:
        await note("blocked", "blocked", layer="pattern", rule_id=rules[0].id)  # F07-AC11
        return error(422, "injection_detected", INJECTION_MESSAGE)
    try:
        async with db.as_principal(principal) as conn:
            await consume(conn, "guard_question", 1)
        verdict = await classify_question(gateway, body.question)
    except QuotaExceeded as exceeded:
        return await quota_refused(db, principal, exceeded)
    except LlmUnavailable:
        await note(
            "question", "error", model=gateway.guard_model, error_code="screening_unavailable"
        )
        return error(503, "screening_unavailable", SCREENING_DOWN)  # fail closed
    except PseudonymizationFailed:
        return await refused()
    if verdict.injection:
        await note("blocked", "blocked", model=gateway.guard_model, layer="classifier")
        return error(422, "injection_detected", INJECTION_MESSAGE)

    try:
        found = await retrieve(
            db, principal, gateway, body.question, body.resident_id, min_similarity
        )
        if not found.hits:
            # no LLM call (AC7)
            model = gateway.embedding_model if found.embedded else None
            return await delivered(reply(NO_HITS_ANSWER, no_hits=True), model)
        async with db.as_principal(principal) as conn:
            await consume(conn, "llm_call", 1)
    except QuotaExceeded as exceeded:
        return await quota_refused(db, principal, exceeded)
    except EmbeddingUnavailable:
        return await unavailable("embedding_unavailable", gateway.embedding_model)
    except PseudonymizationFailed:
        return await refused()

    try:
        answered = await answer_with_sources(gateway, principal, body.question, found.hits)
    except LlmUnavailable:
        return await unavailable("llm_unavailable", gateway.llm_model)
    except PseudonymizationFailed:
        return await refused()
    return await delivered(
        reply(answered.answer, answered.sources, sent=answered.sent), model=gateway.llm_model
    )
