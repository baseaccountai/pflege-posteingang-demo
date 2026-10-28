"""Review, approval and rejection of a suggestion (F03-AC5 to AC11).

Only a human approval writes the record. The approval is one transaction as the caller:
  1. lock the document row and check its status (AC9) - two approvals, or approval against
     rejection, run one after the other; the second sees the new status and is refused;
  2. lock the resident (advisory lock: two plans of the same resident queue up);
  3. compute the medication comparison again and compare it with the one the nurse saw
     (diff_hash); if the record changed in between, refuse with the new comparison (AC8a);
  4. write medications, one event per change, diagnoses and follow-ups - all with the
     document as origin and the confirming user from the claims - and approve the document.
"""

import uuid
from datetime import date
from typing import Literal

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.auth.principal import Principal
from app.db import Database
from app.extraction.medication_diff import SLOTS, Med, MedChange, diff, diff_hash

DocType = Literal["arztbrief", "medikationsplan", "ueberleitungsbogen", "sonstiges"]
RECORD_CHANGED = "Die Akte wurde inzwischen geändert – bitte Abgleich prüfen"


class MedicationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    strength: str | None = Field(default=None, max_length=100)
    dosage: dict[Literal["morgens", "mittags", "abends", "nachts"], str | None] = {}
    hint: str | None = Field(default=None, max_length=500)


class FollowUpIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_date: date | None = None


class ComparisonRequest(BaseModel):
    resident_id: str
    doc_type: DocType
    medications: list[MedicationIn] = []


class Approval(BaseModel):
    resident_id: str
    resident_confirmed: bool
    diff_hash: str
    doc_type: DocType
    document_date: date | None = None
    diagnoses: list[str] = []
    medications: list[MedicationIn] = []
    follow_ups: list[FollowUpIn] = []


class NotFound(Exception):
    """Unknown or foreign document (same answer for both)."""


class Invalid(Exception):
    """Request cannot be accepted as it is -> 422."""

    def __init__(self, error_code: str, message: str):
        super().__init__(error_code)
        self.error_code, self.message = error_code, message


class Conflict(Exception):
    """Wrong status or changed record -> 409 (with the new comparison if there is one)."""

    def __init__(self, error_code: str, message: str, extra: dict | None = None):
        super().__init__(error_code)
        self.error_code, self.message, self.extra = error_code, message, extra or {}


def _med(item: MedicationIn | dict) -> Med:
    data = item if isinstance(item, dict) else item.model_dump()
    dosage = {slot: (data.get("dosage") or {}).get(slot) or "0" for slot in SLOTS}
    return Med(
        name=data["name"], strength=data.get("strength"), dosage=dosage, hint=data.get("hint")
    )


def _side(med: Med | None) -> dict | None:
    if med is None:
        return None
    return {"name": med.name, "strength": med.strength, "dosage": med.dosage, "hint": med.hint}


def changes_json(changes: list[MedChange]) -> list[dict]:
    return [
        {
            "kind": c.kind,
            "name": c.name,
            "medication_id": c.medication_id,
            "before": _side(c.before),
            "after": _side(c.after),
        }
        for c in changes
    ]


async def resident_ward(conn: AsyncConnection, resident_id: str) -> str | None:
    """Ward of a resident the caller may see (RLS), else None."""
    try:
        cur = await conn.execute(
            "select ward_id from public.residents where id = %s::uuid", [resident_id]
        )
    except Exception:  # malformed uuid
        return None
    row = await cur.fetchone()
    return row[0] if row else None


async def comparison(
    conn: AsyncConnection, resident_id: str, doc_type: str, medications: list
) -> tuple[list[MedChange], str]:
    """Medication comparison against the resident's active medications (F03-AC7).

    Only a medication plan lists all medications; for other documents nothing is
    discontinued just because it is not mentioned.
    """
    cur = await conn.execute(
        "select id::text, name, strength, dosage, hint from public.medications"
        " where resident_id = %s and status = 'active' order by created_at",
        [resident_id],
    )
    current = [
        Med(name=name, strength=strength, dosage=dosage or {}, hint=hint, id=med_id)
        for med_id, name, strength, dosage, hint in await cur.fetchall()
    ]
    changes = diff(current, [_med(m) for m in medications])
    if doc_type != "medikationsplan":
        changes = [c for c in changes if c.kind != "discontinued"]
    return changes, diff_hash(changes)


async def _lock_for_review(conn: AsyncConnection, document_id: str) -> str:
    """Locks the document row; returns its ward or raises NotFound/Conflict (F03-AC9)."""
    cur = await conn.execute(
        "select status::text, approved_by_name, ward_id from public.documents"
        " where id = %s for update",
        [document_id],
    )
    row = await cur.fetchone()
    if row is None:
        raise NotFound()
    status, approved_by_name, ward = row
    if status == "approved":
        raise Conflict(
            "already_approved", f"Das Dokument wurde bereits freigegeben von {approved_by_name}."
        )
    if status == "rejected":
        raise Conflict("already_rejected", "Das Dokument wurde bereits verworfen.")
    if status != "ready_for_review":
        raise Conflict("not_ready", "Das Dokument ist nicht bereit zur Prüfung.")
    return ward


UNKNOWN_RESIDENT = ("resident_unknown", "Bewohner nicht gefunden oder in anderem Wohnbereich.")


def canonical_resident(resident_id: str) -> str:
    """One spelling per resident: Postgres reads '1111…' with or without hyphens, in any
    case, as the same uuid - the resident lock below must do the same."""
    try:
        return str(uuid.UUID(resident_id))
    except ValueError as invalid:
        raise Invalid(*UNKNOWN_RESIDENT) from invalid


async def approve(db: Database, principal: Principal, document_id: str, approval: Approval) -> None:
    if not approval.resident_confirmed:
        raise Invalid("resident_not_confirmed", "Bitte den Bewohner bestätigen.")
    approval = approval.model_copy(update={"resident_id": canonical_resident(approval.resident_id)})
    async with db.as_principal(principal) as conn:
        ward = await _lock_for_review(conn, document_id)
        if await resident_ward(conn, approval.resident_id) != ward:
            raise Invalid(*UNKNOWN_RESIDENT)
        # Plans of the same resident are approved one after the other (F03-AC8).
        await conn.execute(
            "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [f"resident:{approval.resident_id}"],
        )
        changes, current_hash = await comparison(
            conn, approval.resident_id, approval.doc_type, approval.medications
        )
        if current_hash != approval.diff_hash:
            raise Conflict(
                "record_changed",
                RECORD_CHANGED,
                {"medication_changes": changes_json(changes), "diff_hash": current_hash},
            )
        await _write_medications(conn, ward, approval.resident_id, document_id, changes)
        for text in filter(None, (d.strip() for d in approval.diagnoses)):
            await conn.execute(
                "insert into public.diagnoses (ward_id, resident_id, text, source_document_id)"
                " values (%s, %s, %s, %s)",
                [ward, approval.resident_id, text, document_id],
            )
        for item in approval.follow_ups:
            await conn.execute(
                "insert into public.follow_ups (ward_id, resident_id, title, due_date,"
                " source_document_id) values (%s, %s, %s, %s, %s)",
                [ward, approval.resident_id, item.title, item.due_date, document_id],
            )
        await conn.execute(
            """
            update public.documents set
              status = 'approved', resident_id = %s, doc_type = %s, document_date = %s,
              approved_by = app.uid(), approved_by_name = app.display_name(),
              approved_at = now(), status_changed_at = now(),
              indexing_status = 'pending'  -- F05 indexes approved documents (F03-AC11)
            where id = %s
            """,
            [approval.resident_id, approval.doc_type, approval.document_date, document_id],
        )


async def _write_medications(
    conn: AsyncConnection, ward: str, resident_id: str, document_id: str, changes: list[MedChange]
) -> None:
    for change in changes:
        if change.kind == "unchanged":
            continue
        if change.kind == "new":
            cur = await conn.execute(
                "insert into public.medications"
                " (ward_id, resident_id, name, strength, dosage, hint)"
                " values (%s, %s, %s, %s, %s, %s) returning id",
                [
                    ward,
                    resident_id,
                    change.after.name,
                    change.after.strength,
                    Jsonb(change.after.dosage),
                    change.after.hint,
                ],
            )
            (medication_id,) = await cur.fetchone()
        elif change.kind == "changed":
            medication_id = change.medication_id
            await conn.execute(
                "update public.medications set strength = %s, dosage = %s, hint = %s where id = %s",
                [
                    change.after.strength,
                    Jsonb(change.after.dosage),
                    change.after.hint,
                    medication_id,
                ],
            )
        else:  # discontinued
            medication_id = change.medication_id
            await conn.execute(
                "update public.medications set status = 'discontinued' where id = %s",
                [medication_id],
            )
        await conn.execute(
            "insert into public.medication_events (ward_id, medication_id, kind, document_id,"
            " before, after) values (%s, %s, %s, %s, %s, %s)",
            [
                ward,
                medication_id,
                change.kind,
                document_id,
                Jsonb(_side(change.before)) if change.before else None,
                Jsonb(_side(change.after)) if change.after else None,
            ],
        )


async def reject(db: Database, principal: Principal, document_id: str) -> None:
    """F03-AC10: rejected documents create no record entries."""
    async with db.as_principal(principal) as conn:
        await _lock_for_review(conn, document_id)
        await conn.execute(
            "update public.documents set status = 'rejected', status_changed_at = now()"
            " where id = %s",
            [document_id],
        )
