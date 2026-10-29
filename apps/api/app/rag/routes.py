"""POST /questions (F05): a question about the documents of the own wards, answered with
sources - or the same "no hits" for everything that cannot be found (F05-AC7).

Order of the paid steps: the question is embedded (embedding quota, in retrieve), and only
if there are hits the LLM is called (LLM quota booked first, F05-AC12, F10-AC10).
The model only sees pseudonymised text (F06, rag/answer.py).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import current_principal
from app.auth.principal import Principal
from app.documents.routes import database, error, quota_error
from app.privacy.gateway import PseudonymizationFailed
from app.providers.embeddings.base import EmbeddingUnavailable
from app.providers.llm.base import LlmUnavailable
from app.quotas import QuotaExceeded, consume
from app.rag.answer import answer_with_sources
from app.rag.retrieval import Hit, retrieve
from app.security.classifier import classify_question
from app.security.patterns import matching_rules

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

    # F07-AC9: rules, then the checker model, see the question before any other model.
    if any(rule.category in QUESTION_CATEGORIES for rule in matching_rules(body.question)):
        return error(422, "injection_detected", INJECTION_MESSAGE)
    try:
        async with db.as_principal(principal) as conn:
            await consume(conn, "guard_question", 1)
        verdict = await classify_question(gateway, body.question)
    except QuotaExceeded as exceeded:
        return quota_error(exceeded)
    except LlmUnavailable:
        return error(503, "screening_unavailable", SCREENING_DOWN)  # fail closed
    except PseudonymizationFailed:
        return reply(REFUSED_ANSWER)
    if verdict.injection:
        return error(422, "injection_detected", INJECTION_MESSAGE)

    try:
        found = await retrieve(
            db, principal, gateway, body.question, body.resident_id, min_similarity
        )
        if not found.hits:
            return reply(NO_HITS_ANSWER, no_hits=True)  # no LLM call (AC7)
        async with db.as_principal(principal) as conn:
            await consume(conn, "llm_call", 1)
    except QuotaExceeded as exceeded:
        return quota_error(exceeded)
    except EmbeddingUnavailable:
        return reply(UNAVAILABLE_ANSWER)
    except PseudonymizationFailed:
        return reply(REFUSED_ANSWER)

    try:
        answered = await answer_with_sources(gateway, principal, body.question, found.hits)
    except LlmUnavailable:
        return reply(UNAVAILABLE_ANSWER)
    except PseudonymizationFailed:
        return reply(REFUSED_ANSWER)
    return reply(answered.answer, answered.sources, sent=answered.sent)
