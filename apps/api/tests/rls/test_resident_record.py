"""F04: resident list with counters, the record with provenance and "follow-up done" -
through the whole API stack against the local database (RLS as the caller)."""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.config import Settings
from app.main import create_app
from tests.rls.conftest import ADMIN_DSN, GATEWAY_DSN, WB1_RESIDENT, WB2_RESIDENT
from tests.support.oidc import (
    AUDIENCE,
    BFF_SECRET,
    ISSUER,
    ROLES_CLAIM,
    access_token,
    bff_assertion,
    test_verifier,
)

pytestmark = pytest.mark.db


@pytest.fixture
def api(seeded: None) -> Iterator[TestClient]:
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
    )
    with TestClient(create_app(settings, verifier=test_verifier())) as client:
        yield client


def as_role(role: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token(f'u-{role}', role)}",
        "X-Bff-Assertion": bff_assertion(),
    }


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def approved_document(
    resident: str = WB1_RESIDENT,
    ward: str = "wb1",
    days_ago: int = 0,
    doc_type: str = "medikationsplan",
    document_date: str = "2026-10-12",
) -> str:
    """An approved document; `days_ago` moves the approval into the past."""
    return admin(
        "insert into public.documents (ward_id, resident_id, uploaded_by, upload_session,"
        " status, doc_type, document_date, approved_by, approved_by_name, approved_at)"
        " values (%s, %s, 'u', 's', 'approved', %s, %s, 'u-nurse', 'Pflegekraft WB1',"
        " now() - make_interval(days => %s)) returning id::text",
        [ward, resident, doc_type, document_date, days_ago],
    )[0][0]


def follow_up(
    due_in_days: int | None,
    resident: str = WB1_RESIDENT,
    ward: str = "wb1",
    status: str = "open",
    document: str | None = None,
    actor_type: str = "human",
) -> str:
    """A follow-up due `due_in_days` from today (Berlin), written with admin rights."""
    return admin(
        "insert into public.follow_ups (ward_id, resident_id, title, due_date, status,"
        " source_document_id, actor_type, created_by, confirmed_by, confirmed_by_name)"
        " values (%s, %s, 'Kontrolle', (now() at time zone 'Europe/Berlin')::date + %s::int,"
        " %s, %s, %s, 'u-nurse', 'u-nurse', 'Pflegekraft WB1') returning id::text",
        [ward, resident, due_in_days, status, document, actor_type],
    )[0][0]


def residents_by_id(api: TestClient, role: str) -> dict[str, dict]:
    response = api.get("/residents", headers=as_role(role))
    assert response.status_code == 200
    return {resident["id"]: resident for resident in response.json()}


# --- F04-AC1: list per role -------------------------------------------------------------


def test_list_shows_only_own_ward_with_name_room_and_ward(api):
    admin("update public.residents set room = '104' where id = %s", [WB1_RESIDENT])
    residents = residents_by_id(api, "nurse_wb1")
    assert list(residents) == [WB1_RESIDENT]
    entry = residents[WB1_RESIDENT]
    assert entry["display_name"] == "Hr. Muster-Bauer"
    assert entry["room"] == "104"
    assert entry["ward_id"] == "wb1"
    assert entry["ward_name"] == "WB 1"


def test_nurse_wb2_sees_only_wb2(api):
    assert list(residents_by_id(api, "nurse_wb2")) == [WB2_RESIDENT]


def test_pdl_sees_all_ordered_by_ward(api):
    # A second WB1 resident whose name sorts after the WB2 one: order is ward first.
    admin(
        "insert into public.residents (ward_id, display_name) values ('wb1', 'Hr. Zett')",
    )
    response = api.get("/residents", headers=as_role("pdl"))
    wards_and_names = [(r["ward_id"], r["display_name"]) for r in response.json()]
    assert wards_and_names == [
        ("wb1", "Hr. Muster-Bauer"),
        ("wb1", "Hr. Zett"),
        ("wb2", "Fr. Testfeld"),
    ]


# --- F04-AC2: "new" badge and follow-up counters -----------------------------------------


def test_document_approved_six_days_ago_is_new(api):
    approved_document(days_ago=6)
    assert residents_by_id(api, "nurse_wb1")[WB1_RESIDENT]["has_new"] is True


def test_document_approved_eight_days_ago_is_not_new(api):
    approved_document(days_ago=8)
    assert residents_by_id(api, "nurse_wb1")[WB1_RESIDENT]["has_new"] is False


def test_unapproved_document_is_not_new(api):
    admin(
        "insert into public.documents (ward_id, resident_id, uploaded_by, upload_session,"
        " status) values ('wb1', %s, 'u', 's', 'rejected')",
        [WB1_RESIDENT],
    )
    assert residents_by_id(api, "nurse_wb1")[WB1_RESIDENT]["has_new"] is False


def test_counts_open_and_due_follow_ups(api):
    follow_up(-1)  # overdue
    follow_up(0)  # due today
    follow_up(3)  # open, not yet due
    follow_up(None)  # open, no due date
    follow_up(-5, status="done")  # done: never counted
    entry = residents_by_id(api, "nurse_wb1")[WB1_RESIDENT]
    assert entry["open_follow_ups"] == 4
    assert entry["overdue_follow_ups"] == 2


def test_resident_without_anything_has_zero_counters(api):
    entry = residents_by_id(api, "nurse_wb1")[WB1_RESIDENT]
    assert entry["has_new"] is False
    assert entry["open_follow_ups"] == 0
    assert entry["overdue_follow_ups"] == 0


def test_counters_of_other_ward_do_not_leak(api):
    follow_up(-1, resident=WB2_RESIDENT, ward="wb2")
    approved_document(resident=WB2_RESIDENT, ward="wb2")
    entry = residents_by_id(api, "pdl")[WB1_RESIDENT]
    assert (entry["has_new"], entry["open_follow_ups"]) == (False, 0)
    other = residents_by_id(api, "pdl")[WB2_RESIDENT]
    assert (other["has_new"], other["open_follow_ups"], other["overdue_follow_ups"]) == (
        True,
        1,
        1,
    )


# --- F04-AC3 to AC6, AC9, AC10: the record ------------------------------------------------

DOSE = {"morgens": "1", "mittags": "0", "abends": "0", "nachts": "0"}


def medication(name: str = "Ramipril", strength: str = "5 mg", status: str = "active") -> str:
    return admin(
        "insert into public.medications (ward_id, resident_id, name, strength, dosage, status,"
        " created_by) values ('wb1', %s, %s, %s, %s, %s, 'seed') returning id::text",
        [WB1_RESIDENT, name, strength, Jsonb(DOSE), status],
    )[0][0]


def event(
    medication_id: str,
    kind: str,
    days_ago: int,
    document: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    actor_type: str = "human",
    confirmed_by_name: str = "Pflegekraft WB1",
) -> None:
    admin(
        "insert into public.medication_events (ward_id, medication_id, kind, document_id,"
        " before, after, actor_type, created_by, confirmed_by, confirmed_by_name, created_at)"
        " values ('wb1', %s, %s, %s, %s, %s, %s, 'u', 'u', %s,"
        " now() - make_interval(days => %s))",
        [
            medication_id,
            kind,
            document,
            Jsonb(before) if before else None,
            Jsonb(after) if after else None,
            actor_type,
            confirmed_by_name,
            days_ago,
        ],
    )


def side(strength: str) -> dict:
    return {"name": "Ramipril", "strength": strength, "dosage": DOSE}


def record(api: TestClient, role: str = "nurse_wb1", resident: str = WB1_RESIDENT):
    return api.get(f"/residents/{resident}/record", headers=as_role(role))


def test_record_has_all_sections(api):
    response = record(api)
    assert response.status_code == 200
    body = response.json()
    assert body["resident"]["id"] == WB1_RESIDENT
    assert body["resident"]["ward_name"] == "WB 1"
    assert body["medications"] == {"active": [], "discontinued": []}
    assert body["diagnoses"] == []
    assert body["follow_ups"] == []
    assert body["documents"] == []


def test_medication_shows_dosage_and_origin_of_latest_change(api):
    first = approved_document(days_ago=20, document_date="2026-10-01")
    second = approved_document(days_ago=2, document_date="2026-10-24", doc_type="arztbrief")
    med = medication(strength="10 mg")
    event(med, "new", 20, first, after=side("5 mg"))
    event(med, "changed", 2, second, before=side("5 mg"), after=side("10 mg"))

    [entry] = record(api).json()["medications"]["active"]
    assert entry["name"] == "Ramipril"
    assert entry["strength"] == "10 mg"
    assert entry["dosage"] == DOSE
    provenance = entry["provenance"]
    assert provenance["document_id"] == second
    assert provenance["doc_type"] == "arztbrief"
    assert provenance["document_date"] == "2026-10-24"
    assert provenance["confirmed_by_name"] == "Pflegekraft WB1"
    assert provenance["actor_type"] == "human"
    assert provenance["confirmed_at"]


def test_full_event_sequence_new_changed_discontinued(api):
    plan = approved_document(days_ago=3)
    med = medication(status="discontinued")
    event(med, "new", 40, before=None, after=side("5 mg"))
    event(med, "changed", 20, before=side("5 mg"), after=side("10 mg"))
    event(med, "discontinued", 3, plan, before=side("10 mg"))

    body = record(api).json()
    assert body["medications"]["active"] == []
    [stopped] = body["medications"]["discontinued"]
    assert [e["kind"] for e in stopped["events"]] == ["new", "changed", "discontinued"]
    assert stopped["events"][1]["before"]["strength"] == "5 mg"
    assert stopped["events"][1]["after"]["strength"] == "10 mg"
    assert stopped["discontinued_at"]
    assert stopped["provenance"]["document_id"] == plan


def test_new_and_changed_within_seven_days_are_marked(api):
    fresh = medication("Metformin", "500 mg")
    event(fresh, "new", 6, after=side("500 mg"))
    changed = medication("Ramipril", "10 mg")
    event(changed, "new", 30, after=side("5 mg"))
    event(changed, "changed", 1, before=side("5 mg"), after=side("10 mg"))
    old = medication("Torasemid", "10 mg")
    event(old, "new", 8, after=side("10 mg"))

    active = {m["name"]: m for m in record(api).json()["medications"]["active"]}
    assert active["Metformin"]["marker"] == "new"
    assert active["Ramipril"]["marker"] == "changed"
    assert active["Ramipril"]["previous"]["strength"] == "5 mg"
    assert active["Torasemid"]["marker"] is None


def test_discontinued_only_shown_for_thirty_days(api):
    recent = medication("Metamizol", status="discontinued")
    event(recent, "discontinued", 29)
    old = medication("Ibuprofen", status="discontinued")
    event(old, "discontinued", 31)
    names = [m["name"] for m in record(api).json()["medications"]["discontinued"]]
    assert names == ["Metamizol"]


def test_diagnoses_and_follow_ups_carry_their_origin(api):
    doc = approved_document(doc_type="arztbrief", document_date="2026-10-12")
    admin(
        "insert into public.diagnoses (ward_id, resident_id, text, source_document_id,"
        " actor_type, created_by, confirmed_by, confirmed_by_name)"
        " values ('wb1', %s, 'Herzinsuffizienz', %s, 'human', 'u', 'u', 'Pflegekraft WB1')",
        [WB1_RESIDENT, doc],
    )
    follow_up(-1, document=doc)
    body = record(api).json()
    [diagnosis] = body["diagnoses"]
    assert diagnosis["text"] == "Herzinsuffizienz"
    assert diagnosis["provenance"]["document_id"] == doc
    assert diagnosis["provenance"]["doc_type"] == "arztbrief"
    assert diagnosis["provenance"]["confirmed_by_name"] == "Pflegekraft WB1"
    [entry] = body["follow_ups"]
    assert entry["title"] == "Kontrolle"
    assert entry["status"] == "open"
    assert entry["overdue"] is True
    assert entry["provenance"]["document_date"] == "2026-10-12"


def test_agent_entries_say_so(api):
    # F04-AC6: written by the agent (seed), confirmed by a human role.
    med = medication()
    event(med, "new", 1, actor_type="agent", confirmed_by_name="Pflegekraft WB1")
    follow_up(2, actor_type="agent")
    body = record(api).json()
    assert body["medications"]["active"][0]["provenance"]["actor_type"] == "agent"
    assert body["follow_ups"][0]["provenance"]["actor_type"] == "agent"


def test_documents_lists_only_approved_ones_of_this_resident(api):
    doc = approved_document(doc_type="arztbrief", document_date="2026-10-12")
    approved_document(resident=WB2_RESIDENT, ward="wb2")
    admin(
        "insert into public.documents (ward_id, resident_id, uploaded_by, upload_session,"
        " status) values ('wb1', %s, 'u', 's', 'rejected')",
        [WB1_RESIDENT],
    )
    [entry] = record(api).json()["documents"]
    assert entry["id"] == doc
    assert entry["doc_type"] == "arztbrief"
    assert entry["document_date"] == "2026-10-12"
    assert entry["approved_by_name"] == "Pflegekraft WB1"


def test_foreign_unknown_and_malformed_record_look_identical(api):
    for resident in (WB1_RESIDENT, str(uuid.uuid4()), "not-a-uuid"):
        response = record(api, role="nurse_wb2", resident=resident)
        assert response.status_code == 404
        assert response.json() == {"detail": "Nicht gefunden"}


def test_pdl_opens_record_of_both_wards(api):
    assert record(api, role="pdl", resident=WB1_RESIDENT).status_code == 200
    assert record(api, role="pdl", resident=WB2_RESIDENT).status_code == 200


def test_open_follow_ups_come_first_by_due_date(api):
    follow_up(-9, status="done")
    follow_up(None)
    follow_up(5)
    follow_up(1)
    entries = record(api).json()["follow_ups"]
    assert [(e["status"], e["overdue"]) for e in entries] == [
        ("open", False),
        ("open", False),
        ("open", False),
        ("done", False),
    ]
    open_due = [e["due_date"] for e in entries[:3]]
    assert open_due[0] < open_due[1] and open_due[2] is None


# --- F04-AC8: follow-up done ----------------------------------------------------------


def done(api: TestClient, follow_up_id: str, role: str = "nurse_wb1"):
    return api.post(f"/follow-ups/{follow_up_id}/done", headers=as_role(role))


def test_marking_done_records_who_and_when(api):
    entry = follow_up(-1)
    response = done(api, entry)
    assert response.status_code == 200
    assert response.json()["status"] == "done"
    [(status, done_by, done_by_name, has_time)] = admin(
        "select status, done_by, done_by_name, done_at is not null from public.follow_ups"
        " where id = %s",
        [entry],
    )
    assert (status, done_by, done_by_name, has_time) == (
        "done",
        "u-nurse_wb1",
        "Pflegekraft WB1",
        True,
    )


def test_done_follow_up_no_longer_counts(api):
    done(api, follow_up(-1))
    entry = residents_by_id(api, "nurse_wb1")[WB1_RESIDENT]
    assert (entry["open_follow_ups"], entry["overdue_follow_ups"]) == (0, 0)


def test_marking_done_twice_is_409(api):
    entry = follow_up(1)
    assert done(api, entry).status_code == 200
    second = done(api, entry, role="pdl")
    assert second.status_code == 409
    # The first one stays recorded.
    assert admin("select done_by from public.follow_ups where id = %s", [entry]) == [
        ("u-nurse_wb1",)
    ]


def test_foreign_unknown_and_malformed_follow_up_are_404(api):
    foreign = follow_up(1, resident=WB2_RESIDENT, ward="wb2")
    for follow_up_id in (foreign, str(uuid.uuid4()), "not-a-uuid"):
        response = done(api, follow_up_id)
        assert response.status_code == 404
        assert response.json() == {"detail": "Nicht gefunden"}
    assert admin("select status from public.follow_ups where id = %s", [foreign]) == [("open",)]


def test_a_medication_shows_its_hint(api):
    # Decision 2A (Codex review Phase 3 #5): "bei Bedarf" belongs into the record (F04-AC4).
    med_id = medication("Metamizol", "500 mg")
    admin("update public.medications set hint = 'bei Bedarf' where id = %s", [med_id])
    event(med_id, "new", 2, after=dict(side("500 mg"), name="Metamizol", hint="bei Bedarf"))
    active = record(api).json()["medications"]["active"]
    assert [(m["name"], m["hint"]) for m in active] == [("Metamizol", "bei Bedarf")]
