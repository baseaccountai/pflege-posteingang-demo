"""F08-AC4, AC10: the five tools run with the agent principal - RLS decides what they see.

The agent works for the nurse of WB1. Everything of WB2 must look exactly like something
that does not exist: same result, no hint that there is more (AC10, like F05-AC7).
"""

import uuid
from datetime import timedelta

import pytest
from psycopg.types.json import Jsonb

from app.agent.tools import ToolContext, call_tool
from app.auth.principal import Principal
from tests.agent.test_tools import berlin_today
from tests.rls.conftest import WB1_RESIDENT, WB2_RESIDENT
from tests.rls.test_record_rls import admin, record  # noqa: F401 (fixture)
from tests.rls.test_retrieval import indexed  # noqa: F401 (fixture)
from tests.support.gateway import db_gateway

pytestmark = [pytest.mark.db, pytest.mark.anyio]

AGENT = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1",
    actor_type="agent",
)  # fmt: skip
UNKNOWN = "99999999-9999-9999-9999-999999999999"


def context(db) -> ToolContext:
    return ToolContext(db=db, principal=AGENT, gateway=db_gateway(db), min_similarity=0.1)


async def tool(db, name: str, **arguments) -> dict:
    return await call_tool(context(db), name, arguments)


@pytest.fixture
def done(record):  # noqa: F811
    """A follow-up of WB1 that is already done: neither tool lists it."""
    admin(
        "insert into public.follow_ups (ward_id, resident_id, title, due_date, status, done_by,"
        " done_by_name, done_at, actor_type, created_by, confirmed_by, confirmed_by_name)"
        " values ('wb1', %s, 'Erledigt', current_date, 'done', 'u-admin', 'Admin', now(),"
        " 'human', 'u-admin', 'u-admin', 'Admin')",
        [WB1_RESIDENT],
    )


def plan(ward: str, name: str) -> str:
    """A medication plan waiting for review: Ramipril raised to 10 mg, Metformin new."""
    doc = str(uuid.uuid4())
    medications = [
        {"name": "Ramipril", "strength": "10 mg", "dosage": {"morgens": "1"}},
        {"name": "Metformin", "strength": "500 mg", "dosage": {"abends": "1"}},
    ]
    suggestion = {
        "resident_name": {"value": name},
        "doc_type": {"value": "medikationsplan"},
        "medications": [{"value": m} for m in medications],
    }
    admin(
        "insert into public.documents (id, ward_id, uploaded_by, upload_session, status,"
        " suggestion) values (%s, %s, 'u-admin', 'sid', 'ready_for_review', %s)",
        [doc, ward, Jsonb(suggestion)],
    )
    return doc


# --- dokumente_durchsuchen ------------------------------------------------------------------


async def test_the_search_finds_documents_of_the_own_ward_only(db, indexed):  # noqa: F811
    result = await tool(db, "dokumente_durchsuchen", frage="Ramipril morgens")
    assert result["treffer"]
    assert {hit["bewohner"] for hit in result["treffer"]} <= {"Hr. Muster-Bauer", "Fr. Zweite"}
    hit = result["treffer"][0]
    assert set(hit) == {
        "dokument_id", "dokumentart", "datum", "bewohner", "bewohner_id", "seite", "text"
    }  # fmt: skip
    assert hit["datum"] == "2026-10-20"


async def test_searching_a_resident_of_another_ward_is_like_searching_nobody(db, indexed):  # noqa: F811
    foreign = await tool(db, "dokumente_durchsuchen", frage="Ramipril", bewohner_id=WB2_RESIDENT)
    unknown = await tool(db, "dokumente_durchsuchen", frage="Ramipril", bewohner_id=UNKNOWN)
    assert foreign == unknown == {"treffer": []}


# --- bewohnerakte_lesen ---------------------------------------------------------------------


async def test_the_agent_reads_the_short_record_of_its_ward(db, record, done):  # noqa: F811
    result = await tool(db, "bewohnerakte_lesen", bewohner_id=WB1_RESIDENT)
    assert result["gefunden"] is True
    assert result["bewohner"] == "Hr. Muster-Bauer"
    assert result["medikation"] == [
        {"name": "Ramipril", "staerke": "5 mg", "dosierung": {"morgens": "1"}, "hinweis": None}
    ]
    assert result["diagnosen"] == ["Hypertonie"]
    assert result["offene_wiedervorlagen"] == [
        {"titel": "Kontrolle", "faellig_am": berlin_today().isoformat(), "ueberfaellig": True}
    ]


async def test_a_record_of_another_ward_is_like_no_record(db, record):  # noqa: F811
    foreign = await tool(db, "bewohnerakte_lesen", bewohner_id=WB2_RESIDENT)
    unknown = await tool(db, "bewohnerakte_lesen", bewohner_id=UNKNOWN)
    assert foreign == unknown == {"gefunden": False}


# --- medikation_abgleichen ------------------------------------------------------------------


async def test_the_comparison_shows_what_the_document_changes(db, record):  # noqa: F811
    doc = plan("wb1", "Herr Muster-Bauer")
    result = await tool(db, "medikation_abgleichen", dokument_id=doc)
    assert result["gefunden"] is True
    assert result["bewohner"] == "Hr. Muster-Bauer"
    kinds = {change["medikament"]: change["art"] for change in result["aenderungen"]}
    assert kinds == {"Ramipril": "geändert", "Metformin": "neu"}
    ramipril = next(c for c in result["aenderungen"] if c["medikament"] == "Ramipril")
    assert ramipril["vorher"]["strength"] == "5 mg"
    assert ramipril["nachher"]["strength"] == "10 mg"


async def test_a_document_of_another_ward_is_like_no_document(db, record):  # noqa: F811
    doc = plan("wb2", "Frau Testfeld")
    foreign = await tool(db, "medikation_abgleichen", dokument_id=doc)
    unknown = await tool(db, "medikation_abgleichen", dokument_id=UNKNOWN)
    assert foreign == unknown == {"gefunden": False}


async def test_without_a_fitting_resident_nothing_is_compared(db, record):  # noqa: F811
    # The name fits only the resident of WB2, whom the agent cannot see.
    doc = plan("wb1", "Frau Testfeld")
    result = await tool(db, "medikation_abgleichen", dokument_id=doc)
    assert result == {"gefunden": True, "bewohner": None, "aenderungen": []}


async def test_a_pdl_agent_compares_only_with_a_resident_of_the_documents_ward(db, record):  # noqa: F811
    # The PDL's agent sees both wards; a WB1 letter about the WB2 resident is not compared.
    pdl_agent = Principal(
        sub="u-pdl", app_role="pdl", ward_ids=("wb1", "wb2"), display_name="PDL",
        actor_type="agent",
    )  # fmt: skip
    ctx = ToolContext(db=db, principal=pdl_agent, gateway=db_gateway(db), min_similarity=0.1)
    doc = plan("wb1", "Frau Testfeld")
    result = await call_tool(ctx, "medikation_abgleichen", {"dokument_id": doc})
    assert result == {"gefunden": True, "bewohner": None, "aenderungen": []}


# --- wiedervorlagen_auflisten ---------------------------------------------------------------


async def test_the_open_follow_ups_of_the_own_ward_are_listed(db, record, done):  # noqa: F811
    result = await tool(db, "wiedervorlagen_auflisten")
    assert result == {
        "wiedervorlagen": [
            {
                "bewohner": "Hr. Muster-Bauer",
                "bewohner_id": WB1_RESIDENT,
                "titel": "Kontrolle",
                "faellig_am": berlin_today().isoformat(),
                "ueberfaellig": True,
            }
        ]
    }


async def test_follow_ups_of_another_ward_are_like_none(db, record):  # noqa: F811
    foreign = await tool(db, "wiedervorlagen_auflisten", bewohner_id=WB2_RESIDENT)
    unknown = await tool(db, "wiedervorlagen_auflisten", bewohner_id=UNKNOWN)
    assert foreign == unknown == {"wiedervorlagen": []}


# --- wiedervorlage_vorschlagen --------------------------------------------------------------


async def test_a_proposal_is_stored_for_the_nurse_and_nothing_else_is_written(db, record):  # noqa: F811
    due = (berlin_today() + timedelta(days=3)).isoformat()
    result = await tool(
        db,
        "wiedervorlage_vorschlagen",
        bewohner_id=WB1_RESIDENT,
        titel="  Blutdruck kontrollieren ",
        faellig_am=due,
    )
    assert result["gefunden"] is True
    assert result["bewohner"] == "Hr. Muster-Bauer"
    assert result["titel"] == "Blutdruck kontrollieren"
    assert result["faellig_am"] == due
    assert result["gueltig_bis"]
    stored = admin(
        "select ward_id, title, due_date::text, created_for, status"
        " from public.agent_proposals where id = %s",
        [result["vorschlag_id"]],
    )
    assert stored == [("wb1", "Blutdruck kontrollieren", due, "u-wb1", "open")]
    # Only a proposal: the follow-up itself is written after a human confirms (AC5).
    assert admin("select count(*) from public.follow_ups where ward_id = 'wb1'") == [(1,)]


async def test_a_proposal_for_another_ward_is_like_one_for_nobody(db, record):  # noqa: F811
    foreign = await tool(db, "wiedervorlage_vorschlagen", bewohner_id=WB2_RESIDENT, titel="X")
    unknown = await tool(db, "wiedervorlage_vorschlagen", bewohner_id=UNKNOWN, titel="X")
    assert foreign == unknown == {"gefunden": False}
    assert admin("select count(*) from public.agent_proposals") == [(0,)]
