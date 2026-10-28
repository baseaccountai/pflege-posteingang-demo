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


MARK_DAYS = 7  # F04-AC4: "neu"/"geändert" for events of the last 7 days
DISCONTINUED_DAYS = 30  # F04-AC4: stopped medications stay visible (struck through) this long

# Provenance (F04-AC5, AC6) of an entry: the document it came from and who confirmed it.
# `d` is the source document (left join: seeded entries may have none), `e` the entry.
PROVENANCE = """
  json_build_object(
    'document_id', d.id::text, 'doc_type', d.doc_type::text, 'document_date', d.document_date,
    'actor_type', e.actor_type, 'confirmed_by_name', e.confirmed_by_name,
    'confirmed_at', e.created_at
  ) as provenance
"""


async def _rows(conn: AsyncConnection, sql: str, params: dict) -> list[dict]:
    cursor = conn.cursor(row_factory=dict_row)
    await cursor.execute(sql, params)
    return await cursor.fetchall()


@router.get("/residents/{resident_id}/record")
async def get_record(resident_id: str, conn: Conn) -> dict:
    """F04-AC3 to AC6, AC10: medications, diagnoses, follow-ups and documents of one
    resident, each entry with its provenance. One query per section, all under RLS."""
    resident = await get_resident(resident_id, conn)  # 404 for foreign/unknown (AC9)
    params = {
        "resident": resident["id"],
        "mark_days": MARK_DAYS,
        "discontinued_days": DISCONTINUED_DAYS,
    }

    medications = await _rows(
        conn,
        "select id::text, name, strength, dosage, hint, status from public.medications"
        " where resident_id = %(resident)s order by name",
        params,
    )
    events = await _rows(
        conn,
        f"""
        select e.medication_id::text, e.kind, e.before, e.after, e.created_at, {PROVENANCE}
        from public.medication_events e
        join public.medications m on m.id = e.medication_id
        left join public.documents d on d.id = e.document_id
        where m.resident_id = %(resident)s
        order by e.created_at, e.id
        """,
        params,
    )
    recent = await _rows(
        conn,
        "select now() - make_interval(days => %(mark_days)s) as marks_since,"
        " now() - make_interval(days => %(discontinued_days)s) as stopped_since",
        params,
    )
    marks_since, stopped_since = recent[0]["marks_since"], recent[0]["stopped_since"]

    active, discontinued = [], []
    for med in medications:
        history = [
            {k: v for k, v in e.items() if k != "medication_id"}
            for e in events
            if e["medication_id"] == med["id"]
        ]
        latest = history[-1] if history else None
        # The origin shown is that of the latest change; the full history unfolds (AC5).
        med["provenance"] = latest["provenance"] if latest else None
        med["events"] = history
        if med["status"] == "discontinued":
            # Without a "discontinued" event we cannot say when or why: not shown.
            if (
                latest
                and latest["kind"] == "discontinued"
                and latest["created_at"] >= stopped_since
            ):
                med["discontinued_at"] = latest["created_at"]
                discontinued.append(med)
            continue
        recent_change = latest and latest["kind"] in ("new", "changed")
        recent_change = recent_change and latest["created_at"] >= marks_since
        med["marker"] = latest["kind"] if recent_change else None
        med["previous"] = (
            latest["before"] if recent_change and latest["kind"] == "changed" else None
        )
        active.append(med)

    diagnoses = await _rows(
        conn,
        f"""
        select e.id::text, e.text, {PROVENANCE}
        from public.diagnoses e
        left join public.documents d on d.id = e.source_document_id
        where e.resident_id = %(resident)s
        order by e.created_at, e.id
        """,
        params,
    )
    follow_ups = await _rows(
        conn,
        f"""
        select e.id::text, e.title, e.due_date, e.status, e.done_by_name, e.done_at,
          coalesce(e.status = 'open' and e.due_date <= {TODAY}, false) as overdue, {PROVENANCE}
        from public.follow_ups e
        left join public.documents d on d.id = e.source_document_id
        where e.resident_id = %(resident)s
        order by e.status = 'done', e.due_date nulls last, e.created_at
        """,
        params,
    )
    documents = await _rows(
        conn,
        "select id::text, doc_type::text, document_date, approved_by_name, approved_at"
        " from public.documents"
        " where resident_id = %(resident)s and status = 'approved'"
        " order by document_date desc nulls last, approved_at desc",
        params,
    )
    return {
        "resident": resident,
        "medications": {"active": active, "discontinued": discontinued},
        "diagnoses": diagnoses,
        "follow_ups": follow_ups,
        "documents": documents,
    }


@router.post("/follow-ups/{follow_up_id}/done")
async def mark_follow_up_done(follow_up_id: str, conn: Conn) -> dict:
    """F04-AC8: an open follow-up becomes done, with the caller and the time.

    Who did it is taken from the claims inside the database (RLS checks it as well).
    Only open rows are updated: of two parallel requests, the second waits for the
    first's row lock, then finds the row done and gets 409.
    """
    follow_up_id = checked_id(follow_up_id)
    cursor = conn.cursor(row_factory=dict_row)
    await cursor.execute(
        "update public.follow_ups set status = 'done', done_by = app.uid(),"
        " done_by_name = app.display_name(), done_at = now()"
        " where id = %s and status = 'open'"
        " returning id::text, status, done_by_name, done_at",
        [follow_up_id],
    )
    row = await cursor.fetchone()
    if row is not None:
        return row
    # Nothing updated: either invisible to the caller (foreign/unknown) or already done.
    await cursor.execute("select 1 from public.follow_ups where id = %s", [follow_up_id])
    if await cursor.fetchone() is None:
        raise NOT_FOUND
    raise HTTPException(status_code=409, detail="Wiedervorlage ist bereits erledigt.")
