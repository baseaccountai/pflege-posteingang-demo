"""Document endpoints (F02): upload, inbox, details, original file, retry.

Order at upload (design F02): ward check -> file check -> quotas -> store, all before any
OCR or LLM call. Quotas and the new rows are one transaction as the caller: if a quota is
used up, nothing is stored and nothing is booked (F02-AC5, F10-AC10).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from psycopg.rows import dict_row

from app.auth.bff import bff_session
from app.auth.dependencies import current_principal
from app.auth.principal import Principal
from app.db import Database
from app.documents.pipeline import Pipeline, mark_stalled
from app.documents.validation import MAX_BYTES, InvalidFile, count_pdf_pages, validate_upload
from app.quotas import QuotaExceeded, consume

router = APIRouter(prefix="/documents")

NOT_FOUND = HTTPException(status_code=404, detail="Nicht gefunden")
DAILY_QUOTA = (
    "Tageskontingent der Demo erreicht – Musterdaten bleiben ansehbar, morgen geht es weiter."
)
SESSION_LIMIT = "Upload-Limit erreicht – Musterdokumente bleiben nutzbar"
LIST_COLUMNS = (
    "id::text, ward_id, doc_type::text, status::text, error_code, attempts,"
    " created_at, status_changed_at"
)

Caller = Annotated[Principal, Depends(current_principal)]
SessionHash = Annotated[str, Depends(bff_session)]


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error_code": code, "message": message})


def quota_error(exceeded: QuotaExceeded) -> JSONResponse:
    if exceeded.kind == "upload":
        return error(429, "session_upload_limit", SESSION_LIMIT)
    return error(429, "daily_quota", DAILY_QUOTA)


def database(request: Request) -> Database:
    if request.app.state.database is None:
        raise HTTPException(status_code=503, detail="Datenbank nicht konfiguriert")
    return request.app.state.database


def pipeline(request: Request) -> Pipeline:
    return request.app.state.pipeline


def checked_id(document_id: str) -> str:
    """Malformed ids get the same 404 as foreign and unknown ones (F01-AC12)."""
    try:
        return str(uuid.UUID(document_id))
    except ValueError as invalid:
        raise NOT_FOUND from invalid


@router.post("", status_code=202)
async def upload_document(
    request: Request,
    background: BackgroundTasks,
    principal: Caller,
    session_hash: SessionHash,
    file: Annotated[bytes, File()],
    ward_id: Annotated[str | None, Form()] = None,
):
    # F02-AC12: nurses upload into their own ward, the PDL chooses one of hers.
    if ward_id is None:
        if len(principal.ward_ids) != 1:
            return error(422, "ward_required", "Bitte einen Wohnbereich wählen.")
        ward_id = principal.ward_ids[0]
    elif ward_id not in principal.ward_ids:
        return error(403, "foreign_ward", "Kein Zugriff auf diesen Wohnbereich.")

    try:
        checked = validate_upload(file[: MAX_BYTES + 1])
    except InvalidFile as invalid:
        return error(invalid.status, invalid.error_code, invalid.message)

    try:
        async with database(request).as_principal(principal) as conn:
            await consume(conn, "upload", 1, subject=session_hash)
            await consume(conn, "ocr_page", checked.pages)
            await consume(conn, "llm_call", 1)
            cur = await conn.execute(
                "insert into public.documents (ward_id, upload_session) values (%s, %s)"
                " returning id::text",
                [ward_id, session_hash],
            )
            (document_id,) = await cur.fetchone()
            await conn.execute(
                "insert into public.document_files (document_id, ward_id, mime, size_bytes,"
                " content) values (%s, %s, %s, %s, %s)",
                [document_id, ward_id, checked.mime, checked.size_bytes, file],
            )
    except QuotaExceeded as exceeded:
        return quota_error(exceeded)

    background.add_task(pipeline(request).run, principal, document_id)
    return {"id": document_id, "status": "uploaded"}


@router.get("")
async def list_documents(request: Request, principal: Caller, status: str | None = None):
    db = database(request)
    await mark_stalled(db, principal)  # F02-AC9, before the list is read
    async with db.as_principal(principal) as conn:
        cur = conn.cursor(row_factory=dict_row)
        # No ward filter on purpose: RLS decides which documents exist for this caller.
        await cur.execute(
            f"select {LIST_COLUMNS} from public.documents"
            " where %(status)s::text is null or status::text = %(status)s"
            " order by created_at desc",
            {"status": status},
        )
        return await cur.fetchall()


@router.get("/{document_id}")
async def get_document(request: Request, principal: Caller, document_id: str):
    async with database(request).as_principal(principal) as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            f"select {LIST_COLUMNS}, ocr_pages, suggestion, suggestion_model"
            " from public.documents where id = %s",
            [checked_id(document_id)],
        )
        row = await cur.fetchone()
    if row is None:
        raise NOT_FOUND
    return row


@router.get("/{document_id}/file")
async def get_file(request: Request, principal: Caller, document_id: str):
    async with database(request).as_principal(principal) as conn:
        cur = await conn.execute(
            "select content, mime from public.document_files where document_id = %s",
            [checked_id(document_id)],
        )
        row = await cur.fetchone()
    if row is None:
        raise NOT_FOUND
    content, mime = row
    # Only the type found by the content check, never sniffed by the browser.
    return Response(
        content=bytes(content),
        media_type=mime,
        headers={
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{document_id}/retry", status_code=202)
async def retry_document(
    request: Request, background: BackgroundTasks, principal: Caller, document_id: str
):
    document_id = checked_id(document_id)
    try:
        async with database(request).as_principal(principal) as conn:
            cur = await conn.execute(
                "select d.status::text, d.ocr_pages is not null, f.content, f.mime"
                " from public.documents d join public.document_files f on f.document_id = d.id"
                " where d.id = %s",
                [document_id],
            )
            row = await cur.fetchone()
            if row is None:
                raise NOT_FOUND
            status, has_ocr, content, mime = row
            if status != "failed":
                return error(409, "not_failed", "Nur fehlgeschlagene Dokumente können neu starten.")
            # The retry continues where it failed and books that step's cost again.
            if not has_ocr:
                pages = count_pdf_pages(bytes(content)) if mime == "application/pdf" else 1
                await consume(conn, "ocr_page", pages)
            await consume(conn, "llm_call", 1)
    except QuotaExceeded as exceeded:
        return quota_error(exceeded)

    background.add_task(pipeline(request).run, principal, document_id)
    return {"id": document_id, "status": "failed"}
