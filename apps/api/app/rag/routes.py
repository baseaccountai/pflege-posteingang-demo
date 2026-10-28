"""POST /questions (F05): a question about the documents of the own wards, answered with
sources - or the same "no hits" for everything that cannot be found (F05-AC7).

Order of the paid steps: the question is embedded (embedding quota, in retrieve), and only
if there are hits the LLM is called (LLM quota booked first, F05-AC12, F10-AC10).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import current_principal
from app.auth.principal import Principal
from app.documents.routes import database, quota_error
from app.providers.embeddings.base import EmbeddingUnavailable
from app.providers.llm.base import LlmInvalidOutput, LlmUnavailable
from app.quotas import QuotaExceeded, consume
from app.rag.answer import ANSWER_SCHEMA, MAX_OUTPUT_TOKENS, build_prompt, check_answer
from app.rag.retrieval import Hit, retrieve

router = APIRouter()

NO_HITS_ANSWER = "Keine Treffer in deinem Wohnbereich."
UNAVAILABLE_ANSWER = "Die Antwort ist gerade nicht möglich – bitte gleich erneut versuchen."

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
    llm, embeddings = request.app.state.llm, request.app.state.embeddings
    min_similarity = request.app.state.settings.rag_min_similarity

    def reply(answer: str, sources: list[Hit] | None = None, no_hits: bool = False) -> dict:
        return {
            "answer": answer,
            "sources": [_source(hit) for hit in sources or []],
            "model": llm.model_name,  # F05-AC10: the app names the model
            "no_hits": no_hits,
        }

    try:
        found = await retrieve(
            db, principal, embeddings, body.question, body.resident_id, min_similarity
        )
        if not found.hits:
            return reply(NO_HITS_ANSWER, no_hits=True)  # no LLM call (AC7)
        async with db.as_principal(principal) as conn:
            await consume(conn, "llm_call", 1)
    except QuotaExceeded as exceeded:
        return quota_error(exceeded)
    except EmbeddingUnavailable:
        return reply(UNAVAILABLE_ANSWER)

    system, user = build_prompt(body.question, found.hits)
    try:
        raw = await llm.structured(system, user, ANSWER_SCHEMA, MAX_OUTPUT_TOKENS)
        text = raw.get("answer", "") if isinstance(raw, dict) else ""
    except LlmUnavailable:
        return reply(UNAVAILABLE_ANSWER)
    except LlmInvalidOutput:
        text = ""  # no usable answer -> no evidence
    checked = check_answer(str(text), found.hits)
    return reply(checked.answer, checked.sources)
