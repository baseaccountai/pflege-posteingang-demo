"""F07-AC9: a text a person sends to a model (a question F05, a task for the agent F08) is
checked before any other model sees it - first the rules, then the checker model.

For such a text only attempts to steer the AI itself count: a nurse may well ask about all
residents of her ward (RLS keeps it there); the rules on data leaks are for documents.
The check fails closed: without the checker model nothing is sent.
"""

from collections.abc import Awaitable, Callable

from app.auth.principal import Principal
from app.db import Database
from app.documents.routes import error, quota_refused
from app.privacy.gateway import ModelGateway, PseudonymizationFailed
from app.providers.llm.base import LlmUnavailable
from app.quotas import QuotaExceeded, consume
from app.security.classifier import UNUSABLE, classify_question
from app.security.evaluation import ATTACK_CATEGORIES
from app.security.patterns import matching_rules

INJECTION_MESSAGE = (
    "Die Anfrage wurde als Versuch erkannt, die Regeln der KI zu umgehen, und nicht ausgeführt."
)
SCREENING_DOWN = (
    "Die Sicherheitsprüfung ist gerade nicht verfügbar – bitte später erneut versuchen."
)
# F07-AC16: the checker answered, but not with a usable verdict. Blocked all the same (fail
# closed), yet the person is not told she attacked the AI - she did nothing wrong.
SCREENING_UNUSABLE = (
    "Die Sicherheitsprüfung lieferte kein verwertbares Ergebnis – bitte erneut versuchen."
)
REQUEST_CATEGORIES = {"ignore_instructions", "role_override", "addresses_ai", "outbound_link"}

Note = Callable[..., Awaitable[bool]]


def checker_rule(category: str) -> str:
    """The checker's category for the audit log (F07-AC16) - only from a fixed list: the
    model writes free text, and the log takes identifiers only (F12-AC3)."""
    name = category.strip().lower()
    return f"classifier:{name if name in ATTACK_CATEGORIES | REQUEST_CATEGORIES else 'other'}"


async def check_request(
    db: Database,
    gateway: ModelGateway,
    principal: Principal,
    text: str,
    note: Note,
    action: str,
    refused: Callable[[], Awaitable[object]],
) -> object | None:
    """None if the text may go on; otherwise the response for the caller.

    `note(action, outcome, **details)` writes the audit event, `action` names the step in it
    (question, agent_task), `refused()` answers a plain name that would have left (F06-AC10).
    """
    rules = [r for r in matching_rules(text) if r.category in REQUEST_CATEGORIES]
    if rules:
        await note("blocked", "blocked", layer="pattern", rule_id=rules[0].id)  # F07-AC11
        return error(422, "injection_detected", INJECTION_MESSAGE)
    try:
        async with db.as_principal(principal) as conn:
            await consume(conn, "guard_question", 1)
        verdict = await classify_question(gateway, text)
    except QuotaExceeded as exceeded:
        return await quota_refused(db, principal, exceeded)
    except LlmUnavailable:
        await note(action, "error", model=gateway.guard_model, error_code="screening_unavailable")
        return error(503, "screening_unavailable", SCREENING_DOWN)  # fail closed
    except PseudonymizationFailed:
        return await refused()
    if verdict.category == UNUSABLE:
        await note(
            "blocked", "blocked", model=gateway.guard_model, layer="classifier",
            error_code="classifier_unusable",
        )  # fmt: skip
        return error(503, "screening_unusable", SCREENING_UNUSABLE)
    if verdict.injection:
        await note(
            "blocked", "blocked", model=gateway.guard_model, layer="classifier",
            rule_id=checker_rule(verdict.category),
        )  # fmt: skip
        return error(422, "injection_detected", INJECTION_MESSAGE)
    return None
