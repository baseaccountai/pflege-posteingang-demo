"""GET /audit (F12-AC6, AC7): the audit log for the PDL, newest first, 50 per page.

The page is continued below the smallest number shown ("Ältere laden"), so new events
arriving meanwhile never shift a page. The query runs as the caller: RLS shows the PDL her
wards and the events without a ward. The 403 for nurses is for a clear message; without it
RLS would simply return nothing.

Resident names are not in the log (F12-AC3); they are looked up when reading, again under
RLS, so the log itself never holds one.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from psycopg.rows import dict_row

from app.auth.dependencies import current_principal
from app.auth.principal import Principal
from app.documents.routes import database, error

router = APIRouter()

PAGE_SIZE = 50
Caller = Annotated[Principal, Depends(current_principal)]


@router.get("/audit")
async def list_audit_events(
    request: Request,
    principal: Caller,
    before: int | None = None,
    agent_only: bool = False,
    blocked_only: bool = False,
):
    if principal.app_role != "pdl":
        return error(403, "pdl_only", "Das Protokoll sieht nur die Pflegedienstleitung.")
    async with database(request).as_principal(principal) as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            """
            select e.id, e.at, e.ward_id, e.action, e.outcome, e.actor_type, e.actor_name,
                   e.on_behalf_of_name, e.model, e.document_id::text, e.resident_id::text,
                   r.display_name as resident_name, e.details
            from public.audit_events e
            left join public.residents r on r.id = e.resident_id
            where (%(before)s::bigint is null or e.id < %(before)s)
              and (not %(agent_only)s or e.actor_type = 'agent')
              and (not %(blocked_only)s or e.outcome = 'blocked')
            order by e.id desc
            limit %(limit)s
            """,
            {
                "before": before,
                "agent_only": agent_only,
                "blocked_only": blocked_only,
                "limit": PAGE_SIZE + 1,  # one more tells whether there is an older page
            },
        )
        rows = await cur.fetchall()
    events = rows[:PAGE_SIZE]
    return {
        "events": [{**e, "at": e["at"].isoformat()} for e in events],
        "next_before": events[-1]["id"] if len(rows) > PAGE_SIZE else None,
    }
