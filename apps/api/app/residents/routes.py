"""Resident endpoints (F01, F04): list with counters, single resident, the record.

Every query runs as the caller (`principal_db`): RLS decides which residents and entries
exist. There is deliberately no ward filter in the SQL - a missing RLS policy would show up
in the tests instead of being hidden by a WHERE clause.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.auth.dependencies import principal_db

router = APIRouter()

NOT_FOUND = HTTPException(status_code=404, detail="Nicht gefunden")
RESIDENT_COLUMNS = "r.id::text, r.ward_id, w.name as ward_name, r.display_name, r.room"
# "Today" is the care home's day, not the database server's UTC day.
TODAY = "(now() at time zone 'Europe/Berlin')::date"
NEW_DAYS = 7  # F04-AC2: a document approved within this many days marks the resident "new"

Conn = Annotated[AsyncConnection, Depends(principal_db)]


def checked_id(resident_id: str) -> str:
    """Malformed, unknown and foreign ids all get the same 404 (F01-AC12)."""
    try:
        return str(uuid.UUID(resident_id))
    except ValueError as invalid:
        raise NOT_FOUND from invalid


@router.get("/residents")
async def list_residents(conn: Conn) -> list[dict]:
    """F04-AC1, F04-AC2: residents ordered by ward (the PDL sees them grouped) with
    the "new" badge and the number of open and due follow-ups."""
    cursor = conn.cursor(row_factory=dict_row)
    await cursor.execute(
        f"""
        select {RESIDENT_COLUMNS},
          exists (
            select 1 from public.documents d
            where d.resident_id = r.id and d.status = 'approved'
              and d.approved_at >= now() - make_interval(days => %(new_days)s)
          ) as has_new,
          (select count(*) from public.follow_ups f
            where f.resident_id = r.id and f.status = 'open')::int as open_follow_ups,
          -- "due" includes today: the follow-up has to be done now (shown red).
          (select count(*) from public.follow_ups f
            where f.resident_id = r.id and f.status = 'open'
              and f.due_date <= {TODAY})::int as overdue_follow_ups
        from public.residents r
        join public.wards w on w.id = r.ward_id
        order by r.ward_id, r.display_name
        """,
        {"new_days": NEW_DAYS},
    )
    return await cursor.fetchall()


@router.get("/residents/{resident_id}")
async def get_resident(resident_id: str, conn: Conn) -> dict:
    cursor = conn.cursor(row_factory=dict_row)
    await cursor.execute(
        f"select {RESIDENT_COLUMNS} from public.residents r"
        " join public.wards w on w.id = r.ward_id where r.id = %s",
        [checked_id(resident_id)],
    )
    row = await cursor.fetchone()
    if row is None:
        raise NOT_FOUND
    return row
