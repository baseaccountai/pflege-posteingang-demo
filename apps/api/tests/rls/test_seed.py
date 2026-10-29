"""F10-AC1: the seed gives two wards with three invented residents each and a record that
already has history: approved documents with files and OCR text, medications with their
events, diagnoses and follow-ups - every entry with its origin.

The seed files are loaded with admin rights (like the reset does); the checks that matter
for the demo run through the API role as WB1, i.e. with RLS.
"""

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.auth.principal import Principal
from app.config import Settings
from app.main import create_app
from tests.rls.conftest import ADMIN_DSN, GATEWAY_DSN, WB1_RESIDENT
from tests.support.oidc import (
    AUDIENCE,
    BFF_SECRET,
    ISSUER,
    ROLES_CLAIM,
    access_token,
    bff_assertion,
    test_verifier,
)

pytestmark = [pytest.mark.db, pytest.mark.anyio]

SEED_DIR = Path(__file__).parents[4] / "supabase" / "seed"
NURSE_WB1 = Principal(
    sub="seed-test", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)


@pytest.fixture
def seed(seeded: None) -> None:
    """Empties the visitor tables and loads supabase/seed/*.sql in name order."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute("truncate public.residents, public.wards cascade")
        for path in sorted(SEED_DIR.glob("*.sql")):
            conn.execute(path.read_text(encoding="utf-8"))


def admin_rows(sql: str) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN) as conn:
        return conn.execute(sql).fetchall()


def test_two_wards_with_three_residents_each(seed: None) -> None:
    rows = admin_rows("select ward_id, count(*) from public.residents group by 1 order by 1")
    assert rows == [("wb1", 3), ("wb2", 3)]
    names = {r[0] for r in admin_rows("select display_name from public.residents")}
    assert names == {
        "Hr. Muster-Bauer",
        "Fr. Beispiel",
        "Hr. Probe",
        "Fr. Testfeld",
        "Hr. Exempel",
        "Fr. Vorlage",
    }


def test_seed_residents_have_fixed_codes(seed: None) -> None:
    # Fixed codes keep the precomputed seed chunks (F10-AC6) valid after every reset.
    rows = admin_rows("select display_name, pseudonym from public.residents order by pseudonym")
    assert rows == [
        ("Fr. Vorlage", "C91"),
        ("Hr. Probe", "D15"),
        ("Fr. Testfeld", "H33"),
        ("Hr. Muster-Bauer", "K42"),
        ("Fr. Beispiel", "R07"),
        ("Hr. Exempel", "W58"),
    ]
    # No code starts with the initial of its surname.
    assert all(code[0] != name.split(" ")[1][0] for name, code in rows)


def test_every_resident_has_an_approved_document_with_file_and_text(seed: None) -> None:
    rows = admin_rows(
        "select r.display_name, count(d.id) from public.residents r"
        " left join public.documents d on d.resident_id = r.id and d.status = 'approved'"
        " and d.ocr_pages is not null and d.approved_at is not null"
        " and exists (select 1 from public.document_files f where f.document_id = d.id"
        "             and f.mime = 'application/pdf' and f.content like '%PDF%'::bytea)"
        " group by 1"
    )
    assert len(rows) == 6
    assert all(count >= 1 for _, count in rows), rows


def test_every_medication_has_events_from_a_document(seed: None) -> None:
    orphans = admin_rows(
        "select m.name from public.medications m where not exists ("
        " select 1 from public.medication_events e where e.medication_id = m.id"
        " and e.document_id is not null)"
    )
    assert orphans == []
    stopped = admin_rows(
        "select m.name from public.medications m join public.medication_events e"
        " on e.medication_id = m.id and e.kind = 'discontinued' where m.status = 'discontinued'"
    )
    assert stopped, "at least one discontinued medication with its event (F04 shows only those)"
    assert admin_rows("select 1 from public.medication_events where kind = 'changed'")


def test_record_entries_name_who_confirmed_them(seed: None) -> None:
    for table in ("medication_events", "diagnoses", "follow_ups"):
        missing = admin_rows(
            f"select count(*) from public.{table}"
            " where confirmed_by_name not in ('Pflegekraft WB1', 'Pflegekraft WB2')"
        )
        assert missing == [(0,)], table
    assert admin_rows("select count(*) > 0 from public.diagnoses") == [(True,)]
    unlinked = admin_rows("select count(*) from public.diagnoses where source_document_id is null")
    assert unlinked == [(0,)]


def test_one_entry_was_created_by_the_agent(seed: None) -> None:
    rows = admin_rows(
        "select 'follow_up' from public.follow_ups where actor_type = 'agent'"
        " union all select 'diagnosis' from public.diagnoses where actor_type = 'agent'"
        " union all select 'event' from public.medication_events where actor_type = 'agent'"
    )
    assert len(rows) == 1


def test_follow_ups_cover_open_overdue_and_done(seed: None) -> None:
    rows = admin_rows(
        "select status, coalesce(due_date <= current_date, false) from public.follow_ups"
    )
    assert ("open", True) in rows  # overdue (F04 counter)
    assert ("open", False) in rows
    assert any(status == "done" for status, _ in rows)


async def test_nurse_sees_the_seeded_record_with_markers(seed: None, db) -> None:
    async with db.as_principal(NURSE_WB1) as conn:
        residents = await (await conn.execute("select id from public.residents")).fetchall()
        assert len(residents) == 3  # WB1 only, through RLS
        meds = await (
            await conn.execute(
                "select name, strength, status from public.medications where resident_id = %s"
                " order by name",
                [WB1_RESIDENT],
            )
        ).fetchall()
    # The record of Hr. Muster-Bauer is older than samples/medikationsplan_muster-bauer.pdf,
    # so uploading that plan shows one new, one changed and one stopped medication.
    assert meds == [
        ("Metformin", "500 mg", "active"),
        ("Ramipril", "5 mg", "active"),
        ("Simvastatin", "20 mg", "active"),
    ]


def test_loading_the_seed_twice_after_emptying_gives_the_same_state(seed: None) -> None:
    query = (
        "select (select count(*) from public.documents), (select count(*) from public.medications),"
        " (select count(*) from public.medication_events), (select count(*) from public.diagnoses),"
        " (select count(*) from public.follow_ups)"
    )
    first = admin_rows(query)
    assert all(count > 0 for count in first[0])
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute("truncate public.residents, public.wards cascade")
        for path in sorted(SEED_DIR.glob("*.sql")):
            conn.execute(path.read_text(encoding="utf-8"))
    assert admin_rows(query) == first


# --- Through the API, as the demo shows it (F04 on top of the seed) ------------------------
BEISPIEL = "33333333-3333-3333-3333-333333333333"


@pytest.fixture
def api(seed: None) -> Iterator[TestClient]:
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
    )
    with TestClient(create_app(settings, verifier=test_verifier())) as client:
        yield client


def headers(role: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token(f'u-{role}', role)}",
        "X-Bff-Assertion": bff_assertion(),
    }


def test_the_resident_list_shows_markers_and_counters(api) -> None:
    response = api.get("/residents", headers=headers("nurse_wb1"))
    rows = {r["display_name"]: r for r in response.json()}
    assert set(rows) == {"Hr. Muster-Bauer", "Fr. Beispiel", "Hr. Probe"}
    assert rows["Fr. Beispiel"]["has_new"] is True
    assert rows["Fr. Beispiel"]["open_follow_ups"] == 2
    assert rows["Fr. Beispiel"]["overdue_follow_ups"] == 1
    assert rows["Hr. Muster-Bauer"]["has_new"] is False


def test_the_record_shows_history_origin_and_the_agent_entry(api) -> None:
    record = api.get(f"/residents/{BEISPIEL}/record", headers=headers("nurse_wb1")).json()
    active = {m["name"]: m for m in record["medications"]["active"]}
    assert active["Metamizol"]["marker"] == "new"
    assert active["Metamizol"]["provenance"]["doc_type"] == "arztbrief"
    stopped = [m["name"] for m in record["medications"]["discontinued"]]
    assert stopped == ["Ibuprofen"]
    agent = [f for f in record["follow_ups"] if f["provenance"]["actor_type"] == "agent"]
    assert [f["title"] for f in agent] == ["Termin Orthopädie vereinbaren"]
    assert agent[0]["provenance"]["confirmed_by_name"] == "Pflegekraft WB1"
    assert len(record["documents"]) == 2
