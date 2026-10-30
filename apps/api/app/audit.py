"""Events for the audit log of the care manager (F12), written by the backend.

State changes (upload, status, approval, record entries) are written by database triggers;
the backend cannot create those. This module writes the rest through `app.log_event`:

    ocr | screening | extraction | question      after the model call, outcome ok or error
    blocked                                       F06-AC10 plain name, F07-AC11 each finding
    quota_exhausted                               error_code = the quota kind, e.g. llm_call

Each event is written in a short transaction of its own, after the call (F12-AC8): model
calls run outside of database transactions. Who acted is taken by the database from the
claims of the session, never from here. Details are identifiers only (rule id, layer,
error code, page numbers) - never a text, a question or a name (F12-AC3).
"""

from psycopg import Error as DatabaseError
from psycopg.types.json import Jsonb

from app.auth.principal import Principal
from app.db import Database


class AuditFailed(Exception):
    """The event could not be written; the result it describes must not be passed on."""


async def log(
    db: Database,
    principal: Principal,
    action: str,
    outcome: str = "ok",
    *,
    model: str | None = None,
    document_id: str | None = None,
    **details: object,
) -> None:
    try:
        async with db.as_principal(principal) as conn:
            await conn.execute(
                "select app.log_event(%s, %s, %s, %s, null, %s)",
                [action, outcome, model, document_id, Jsonb(details)],
            )
    except DatabaseError as error:
        raise AuditFailed(str(error)) from error
