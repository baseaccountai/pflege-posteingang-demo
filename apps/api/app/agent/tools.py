"""The agent's five tools (F08-AC4) and how a call is checked (AC10).

How a tool call runs:
1. The model names a tool and passes arguments (JSON from Function Calling).
2. `call_tool` checks three things before anything touches the database:
   - the tool exists (exactly the five below - there is no writing tool besides the proposal),
   - the arguments fit the tool's Pydantic model (types, lengths, no extra fields),
   - the caller is the agent principal (actor_type = 'agent').
   Each failure raises ToolRefused; the runner (A5) turns it into a "blocked" event.
3. The tool runs as the agent: every query goes through `db.as_principal(agent)`, so RLS
   decides what exists. There is no ward filter in the SQL - and a resident or document of
   another ward gives the same result as one that does not exist (AC10).

Results are plain dicts with German keys (the model answers in German). Text from documents
comes back as it is stored; the runner marks it as data (F07-AC8) and the gateway
pseudonymises it before it reaches the model (F06).
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from psycopg.rows import dict_row
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from app.auth.principal import Principal
from app.db import Database
from app.documents.approval import comparison, resident_ward
from app.documents.routes import prefilled_medications
from app.extraction.resident_match import suggest_resident
from app.privacy.gateway import ModelGateway
from app.rag.retrieval import retrieve
from app.residents.routes import TODAY, get_record

MAX_FOLLOW_UPS = 20  # enough for one ward; keeps the tool result small for the model
NOT_FOUND = {"gefunden": False}  # foreign and unknown look exactly alike (AC10)
KIND = {
    "new": "neu",
    "changed": "geändert",
    "discontinued": "abgesetzt",
    "unchanged": "unverändert",
}


@dataclass(frozen=True)
class ToolContext:
    db: Database
    principal: Principal  # the agent: the nurse's identity with actor_type = 'agent'
    gateway: ModelGateway
    min_similarity: float  # for the search, as in F05


class ToolRefused(Exception):
    """The call was not run. reason: unknown_tool, invalid_arguments or not_an_agent."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an unexpected field is refused, not ignored


# --- arguments ------------------------------------------------------------------------------

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class SearchArgs(Arguments):
    frage: str = Field(min_length=1, max_length=500, description="Wonach gesucht wird.")
    bewohner_id: uuid.UUID | None = Field(None, description="Nur Dokumente dieses Bewohners.")


class ResidentArgs(Arguments):
    bewohner_id: uuid.UUID = Field(description="ID des Bewohners.")


class DocumentArgs(Arguments):
    dokument_id: uuid.UUID = Field(description="ID des Dokuments.")


class FollowUpListArgs(Arguments):
    bewohner_id: uuid.UUID | None = Field(None, description="Nur Wiedervorlagen dieses Bewohners.")


class ProposalArgs(Arguments):
    bewohner_id: uuid.UUID = Field(description="ID des Bewohners.")
    titel: Title = Field(description="Was zu tun ist, höchstens 120 Zeichen.")
    faellig_am: date | None = Field(None, description="Fälligkeitsdatum (JJJJ-MM-TT), ab heute.")

    @field_validator("faellig_am")
    @classmethod
    def not_in_the_past(cls, due: date | None) -> date | None:
        # "Today" is the care home's day (Europe/Berlin), as everywhere in the record.
        if due is not None and due < datetime.now(ZoneInfo("Europe/Berlin")).date():
            raise ValueError("Fälligkeit liegt in der Vergangenheit")
        return due


# --- the tools ------------------------------------------------------------------------------


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


async def search_documents(ctx: ToolContext, args: SearchArgs) -> dict:
    """F05 search with the agent's rights (uses one unit of the embedding quota)."""
    resident = str(args.bewohner_id) if args.bewohner_id else None
    found = await retrieve(
        ctx.db, ctx.principal, ctx.gateway, args.frage, resident, ctx.min_similarity
    )
    return {
        "treffer": [
            {
                "dokument_id": hit.document_id,
                "dokumentart": hit.doc_type,
                "datum": _day(hit.document_date),
                "bewohner": hit.resident_name,
                "bewohner_id": hit.resident_id,  # for the next tool (record, proposal)
                "seite": hit.page,
                "text": hit.content,
            }
            for hit in found.hits
        ]
    }


async def read_record(ctx: ToolContext, args: ResidentArgs) -> dict:
    """The record of F04, shortened to what the agent needs (no birth date, no history)."""
    async with ctx.db.as_principal(ctx.principal) as conn:
        try:
            record = await get_record(str(args.bewohner_id), conn)
        except HTTPException:  # 404: foreign or unknown
            return NOT_FOUND
    return {
        "gefunden": True,
        "bewohner": record["resident"]["display_name"],
        "zimmer": record["resident"]["room"],
        "medikation": [
            {
                "name": med["name"],
                "staerke": med["strength"],
                "dosierung": med["dosage"],
                "hinweis": med["hint"],
            }
            for med in record["medications"]["active"]
        ],
        "diagnosen": [diagnosis["text"] for diagnosis in record["diagnoses"]],
        "offene_wiedervorlagen": [
            {"titel": f["title"], "faellig_am": _day(f["due_date"]), "ueberfaellig": f["overdue"]}
            for f in record["follow_ups"]
            if f["status"] == "open"
        ],
    }


async def compare_medication(ctx: ToolContext, args: DocumentArgs) -> dict:
    """Document against the current record: new / changed / discontinued / unchanged (F03)."""
    async with ctx.db.as_principal(ctx.principal) as conn:
        cur = await conn.execute(
            "select ward_id, resident_id::text, doc_type::text, suggestion"
            " from public.documents where id = %s",
            [str(args.dokument_id)],
        )
        row = await cur.fetchone()
        if row is None:
            return NOT_FOUND
        ward, resident, doc_type, suggestion = row
        suggestion = suggestion or {}
        if resident is None:
            # Not approved yet: the resident the review page would suggest (F03-AC5).
            name = (suggestion.get("resident_name") or {}).get("value")
            resident = await suggest_resident(conn, name)
        # A PDL's agent sees two wards: only a resident of the document's ward counts.
        if resident is None or await resident_ward(conn, resident) != ward:
            return {"gefunden": True, "bewohner": None, "aenderungen": []}
        doc_type = doc_type or (suggestion.get("doc_type") or {}).get("value") or "sonstiges"
        changes, _ = await comparison(conn, resident, doc_type, prefilled_medications(suggestion))
        cur = await conn.execute(
            "select display_name from public.residents where id = %s", [resident]
        )
        (name,) = await cur.fetchone()
    return {
        "gefunden": True,
        "bewohner": name,
        "dokumentart": doc_type,
        "aenderungen": [
            {
                "art": KIND[change.kind],
                "medikament": change.name,
                "vorher": _med(change.before),
                "nachher": _med(change.after),
            }
            for change in changes
        ],
    }


def _med(med) -> dict | None:
    if med is None:
        return None
    return {"name": med.name, "strength": med.strength, "dosage": med.dosage, "hint": med.hint}


async def list_follow_ups(ctx: ToolContext, args: FollowUpListArgs) -> dict:
    """Open follow-ups of the own wards (or of one resident), the most urgent first."""
    async with ctx.db.as_principal(ctx.principal) as conn:
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            f"""
            select r.display_name, r.id::text as resident_id, f.title, f.due_date,
              coalesce(f.due_date <= {TODAY}, false) as overdue
            from public.follow_ups f
            join public.residents r on r.id = f.resident_id
            where f.status = 'open'
              and (%(resident)s::uuid is null or f.resident_id = %(resident)s::uuid)
            order by f.due_date nulls last, f.created_at
            limit %(limit)s
            """,
            {
                "resident": str(args.bewohner_id) if args.bewohner_id else None,
                "limit": MAX_FOLLOW_UPS,
            },
        )
        rows = await cur.fetchall()
    return {
        "wiedervorlagen": [
            {
                "bewohner": row["display_name"],
                "bewohner_id": row["resident_id"],
                "titel": row["title"],
                "faellig_am": _day(row["due_date"]),
                "ueberfaellig": row["overdue"],
            }
            for row in rows
        ]
    }


async def propose_follow_up(ctx: ToolContext, args: ProposalArgs) -> dict:
    """The only writing tool: a proposal. The follow-up exists only after a human confirms
    it (A6); RLS lets the agent insert nothing else (F08-AC7)."""
    async with ctx.db.as_principal(ctx.principal) as conn:
        cur = await conn.execute(
            "select ward_id, display_name from public.residents where id = %s",
            [str(args.bewohner_id)],
        )
        row = await cur.fetchone()
        if row is None:
            return NOT_FOUND
        ward, name = row
        cur = await conn.execute(
            "insert into public.agent_proposals (ward_id, resident_id, title, due_date)"
            " values (%s, %s, %s, %s) returning id::text, expires_at",
            [ward, str(args.bewohner_id), args.titel, args.faellig_am],
        )
        proposal, expires_at = await cur.fetchone()
    return {
        "gefunden": True,
        "vorschlag_id": proposal,
        "bewohner": name,
        "titel": args.titel,
        "faellig_am": _day(args.faellig_am),
        "gueltig_bis": expires_at.isoformat(),
    }


# --- registry and call ----------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    description: str
    arguments: type[Arguments]
    run: Callable[[ToolContext, Any], Awaitable[dict]]


TOOLS: dict[str, Tool] = {
    "dokumente_durchsuchen": Tool(
        "Durchsucht die freigegebenen Dokumente des eigenen Wohnbereichs.",
        SearchArgs,
        search_documents,
    ),
    "bewohnerakte_lesen": Tool(
        "Liest die Akte eines Bewohners: aktive Medikation, Diagnosen, offene Wiedervorlagen.",
        ResidentArgs,
        read_record,
    ),
    "medikation_abgleichen": Tool(
        "Vergleicht die Medikation eines Dokuments mit der aktuellen Akte "
        "(neu, geändert, abgesetzt, unverändert).",
        DocumentArgs,
        compare_medication,
    ),
    "wiedervorlagen_auflisten": Tool(
        "Listet offene Wiedervorlagen des Wohnbereichs oder eines Bewohners.",
        FollowUpListArgs,
        list_follow_ups,
    ),
    "wiedervorlage_vorschlagen": Tool(
        "Schlägt eine Wiedervorlage vor. Sie wird erst angelegt, wenn die Pflegekraft "
        "sie bestätigt.",
        ProposalArgs,
        propose_follow_up,
    ),
}


def tool_schemas() -> list[dict]:
    """The tools in the format of Function Calling (Mistral and Ollama use the same)."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool.description,
                "parameters": tool.arguments.model_json_schema(),
            },
        }
        for name, tool in TOOLS.items()
    ]


async def call_tool(ctx: ToolContext, name: str, arguments: Any) -> dict:
    if ctx.principal.actor_type != "agent":
        raise ToolRefused("not_an_agent")
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolRefused("unknown_tool")
    try:
        args = tool.arguments.model_validate(arguments)
    except ValidationError as invalid:
        raise ToolRefused("invalid_arguments") from invalid
    return await tool.run(ctx, args)
