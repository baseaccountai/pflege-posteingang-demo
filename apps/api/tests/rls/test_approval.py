"""F03-AC5 to AC11: suggestion, medication comparison, approval and rejection - against the
local database as the caller (RLS), with parallel requests where order matters."""

import asyncio
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.auth.principal import Principal
from app.config import Settings
from app.documents.approval import Approval, Conflict, approve, reject
from app.main import create_app
from app.providers.llm.fake import FakeLlm
from app.providers.ocr.fake import FakeOcr
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

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-nurse_wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
DOSE = {"morgens": "1", "mittags": "0", "abends": "0", "nachts": "0"}


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def med(name: str, strength: str) -> dict:
    return {"name": name, "strength": strength, "dosage": DOSE, "hint": None}


def found(value) -> dict:
    return {"value": value, "proposed": value, "evidence": "x", "evidence_found": True}


def review_document(
    ward: str = "wb1", doc_type: str = "medikationsplan", meds=(), name="Hr. Muster-Bauer"
) -> str:
    doc = str(uuid.uuid4())
    suggestion = {
        "doc_type": found(doc_type),
        "document_date": found("2026-10-22"),
        "issuer": found("Hausarztpraxis Dr. Ipsum"),
        "resident_name": found(name),
        "diagnoses": [found("Herzinsuffizienz")],
        "medications": [found(m) for m in meds],
        "follow_ups": [found({"title": "Kontrolle", "due_date": "2026-11-05"})],
    }
    admin(
        "insert into public.documents (id, ward_id, uploaded_by, upload_session, status,"
        " suggestion, suggestion_model) values (%s, %s, 'u', 's', 'ready_for_review', %s, 'fake')",
        [doc, ward, Jsonb(suggestion)],
    )
    return doc


def record_med(name: str, strength: str, resident: str = WB1_RESIDENT, ward: str = "wb1") -> str:
    return admin(
        "insert into public.medications (ward_id, resident_id, name, strength, dosage, created_by)"
        " values (%s, %s, %s, %s, %s, 'seed') returning id::text",
        [ward, resident, name, strength, Jsonb(DOSE)],
    )[0][0]


@pytest.fixture
def api(seeded) -> Iterator[TestClient]:
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
    )
    app = create_app(settings, verifier=test_verifier(), ocr=FakeOcr(), llm=FakeLlm())
    with TestClient(app) as client:
        yield client


def headers(role: str = "nurse_wb1") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token(f'u-{role}', role)}",
        "X-Bff-Assertion": bff_assertion(),
    }


def body(doc_hash: str, meds: list[dict], resident=WB1_RESIDENT, confirmed=True, **over) -> dict:
    data = {
        "resident_id": resident,
        "resident_confirmed": confirmed,
        "diff_hash": doc_hash,
        "doc_type": "medikationsplan",
        "document_date": "2026-10-22",
        "diagnoses": ["Herzinsuffizienz"],
        "medications": meds,
        "follow_ups": [{"title": "Kontrolle", "due_date": "2026-11-05"}],
    }
    data.update(over)
    return data


# --- suggestion and comparison --------------------------------------------------------------


def test_suggestion_with_resident_candidate_and_medication_changes(api):
    record_med("Ramipril", "5 mg")
    record_med("Simvastatin", "20 mg")
    doc = review_document(meds=[med("Ramipril", "5 mg"), med("Torasemid", "10 mg")])
    answer = api.get(f"/documents/{doc}/suggestion", headers=headers()).json()

    assert answer["model"] == "fake"
    assert answer["resident_candidate"] == WB1_RESIDENT
    kinds = {c["name"]: c["kind"] for c in answer["medication_changes"]}
    assert kinds == {"Ramipril": "unchanged", "Torasemid": "new", "Simvastatin": "discontinued"}
    assert len(answer["diff_hash"]) == 64


def test_no_candidate_when_the_name_fits_nobody_in_the_own_ward(api):
    doc = review_document(name="Fr. Testfeld")  # lives in WB2
    answer = api.get(f"/documents/{doc}/suggestion", headers=headers()).json()
    assert answer["resident_candidate"] is None
    assert answer["medication_changes"] == []


def test_comparison_is_recomputed_for_another_resident(api):
    record_med("Ramipril", "5 mg")
    doc = review_document()
    other = str(uuid.uuid4())
    admin(
        "insert into public.residents (id, ward_id, display_name) values (%s, 'wb1', 'Hr. Probe')",
        [other],
    )
    meds = [med("Ramipril", "5 mg")]
    for resident, kind in [(WB1_RESIDENT, "unchanged"), (other, "new")]:
        answer = api.post(
            f"/documents/{doc}/medication-diff",
            headers=headers(),
            json={"resident_id": resident, "doc_type": "medikationsplan", "medications": meds},
        ).json()
        assert [c["kind"] for c in answer["medication_changes"]] == [kind]


def test_an_arztbrief_does_not_discontinue_medications(api):
    record_med("Simvastatin", "20 mg")
    doc = review_document(doc_type="arztbrief")
    answer = api.post(
        f"/documents/{doc}/medication-diff",
        headers=headers(),
        json={"resident_id": WB1_RESIDENT, "doc_type": "arztbrief", "medications": []},
    ).json()
    assert answer["medication_changes"] == []


def test_foreign_documents_and_residents_are_not_found(api):
    doc = review_document(ward="wb2", name="Fr. Testfeld")
    assert api.get(f"/documents/{doc}/suggestion", headers=headers()).status_code == 404
    own = review_document()
    answer = api.post(
        f"/documents/{own}/medication-diff",
        headers=headers(),
        json={"resident_id": WB2_RESIDENT, "doc_type": "medikationsplan", "medications": []},
    )
    assert answer.status_code == 422


# --- approval -------------------------------------------------------------------------------


def current_hash(api, doc, meds, resident=WB1_RESIDENT, doc_type="medikationsplan") -> str:
    return api.post(
        f"/documents/{doc}/medication-diff",
        headers=headers(),
        json={"resident_id": resident, "doc_type": doc_type, "medications": meds},
    ).json()["diff_hash"]


def test_approval_writes_the_record_with_origin_and_events(api):
    ramipril = record_med("Ramipril", "5 mg")
    simva = record_med("Simvastatin", "20 mg")
    meds = [med("Ramipril", "10 mg"), med("Torasemid", "10 mg")]
    doc = review_document(meds=meds)

    answer = api.post(
        f"/documents/{doc}/approve",
        headers=headers(),
        json=body(current_hash(api, doc, meds), meds),
    )
    assert answer.status_code == 200

    status, resident, by_name, indexing = admin(
        "select status::text, resident_id::text, approved_by_name, indexing_status::text"
        " from public.documents where id = %s",
        [doc],
    )[0]
    assert (status, resident, by_name, indexing) == (
        "approved",
        WB1_RESIDENT,
        "Pflegekraft WB1",
        "pending",
    )
    events = admin(
        "select m.name, e.kind, e.before->>'strength', e.after->>'strength', e.confirmed_by_name,"
        " e.actor_type, e.document_id::text from public.medication_events e"
        " join public.medications m on m.id = e.medication_id order by m.name"
    )
    assert events == [
        ("Ramipril", "changed", "5 mg", "10 mg", "Pflegekraft WB1", "human", doc),
        ("Simvastatin", "discontinued", "20 mg", None, "Pflegekraft WB1", "human", doc),
        ("Torasemid", "new", None, "10 mg", "Pflegekraft WB1", "human", doc),
    ]
    assert admin("select status, strength from public.medications where id = %s", [ramipril]) == [
        ("active", "10 mg")
    ]
    assert admin("select status from public.medications where id = %s", [simva]) == [
        ("discontinued",)
    ]
    assert admin("select text, source_document_id::text from public.diagnoses") == [
        ("Herzinsuffizienz", doc)
    ]
    assert admin("select title, due_date::text, confirmed_by_name from public.follow_ups") == [
        ("Kontrolle", "2026-11-05", "Pflegekraft WB1")
    ]


def test_approval_without_confirmed_resident_is_refused(api):
    doc = review_document()
    answer = api.post(
        f"/documents/{doc}/approve",
        headers=headers(),
        json=body(current_hash(api, doc, []), [], confirmed=False),
    )
    assert answer.status_code == 422
    assert admin("select status::text from public.documents where id = %s", [doc]) == [
        ("ready_for_review",)
    ]


def test_approval_for_a_resident_of_another_ward_is_refused(api):
    doc = review_document()
    answer = api.post(
        f"/documents/{doc}/approve",
        headers=headers(),
        json=body("0" * 64, [], resident=WB2_RESIDENT),
    )
    assert answer.status_code == 422
    assert admin("select count(*) from public.diagnoses") == [(0,)]


def test_a_changed_record_since_the_comparison_is_refused_with_the_new_comparison(api):
    record_med("Ramipril", "5 mg")
    first_meds = [med("Ramipril", "5 mg")]
    first = review_document(meds=first_meds)
    shown_hash = current_hash(api, first, first_meds)

    # Meanwhile a second plan for the same resident is approved: Ramipril goes to 10 mg.
    second_meds = [med("Ramipril", "10 mg")]
    second = review_document(meds=second_meds)
    api.post(
        f"/documents/{second}/approve",
        headers=headers(),
        json=body(current_hash(api, second, second_meds), second_meds),
    )

    answer = api.post(
        f"/documents/{first}/approve", headers=headers(), json=body(shown_hash, first_meds)
    )
    assert answer.status_code == 409
    assert answer.json()["error_code"] == "record_changed"
    assert answer.json()["message"] == "Die Akte wurde inzwischen geändert – bitte Abgleich prüfen"
    assert [c["kind"] for c in answer.json()["medication_changes"]] == ["changed"]
    assert answer.json()["diff_hash"] != shown_hash


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("processing", "Das Dokument ist nicht bereit zur Prüfung."),
        ("rejected", "Das Dokument wurde bereits verworfen."),
    ],
)
def test_approval_in_the_wrong_status_is_refused(api, status, message):
    doc = review_document()
    admin("update public.documents set status = %s where id = %s", [status, doc])
    for action in ["approve", "reject"]:
        answer = api.post(f"/documents/{doc}/{action}", headers=headers(), json=body("0" * 64, []))
        assert answer.status_code == 409
        assert answer.json()["message"] == message


def test_a_second_approval_names_who_approved(api):
    doc = review_document()
    approval = body(current_hash(api, doc, []), [])
    assert (
        api.post(f"/documents/{doc}/approve", headers=headers(), json=approval).status_code == 200
    )
    again = api.post(f"/documents/{doc}/approve", headers=headers(), json=approval)
    assert again.status_code == 409
    assert again.json()["message"] == "Das Dokument wurde bereits freigegeben von Pflegekraft WB1."


def test_rejection_creates_no_record_entries(api):
    doc = review_document(meds=[med("Torasemid", "10 mg")])
    assert api.post(f"/documents/{doc}/reject", headers=headers()).status_code == 200
    assert admin("select status::text from public.documents where id = %s", [doc]) == [
        ("rejected",)
    ]
    assert admin("select count(*) from public.medications") == [(0,)]


# --- parallel requests (service level: two real transactions at once) -----------------------


def approval_of(doc: str, meds: list[dict], diff_hash: str) -> Approval:
    return Approval(
        resident_id=WB1_RESIDENT,
        resident_confirmed=True,
        diff_hash=diff_hash,
        doc_type="medikationsplan",
        document_date="2026-10-22",
        diagnoses=["Herzinsuffizienz"],
        medications=meds,
        follow_ups=[],
    )


async def outcome(coro) -> str:
    try:
        await coro
        return "ok"
    except Conflict:
        return "conflict"


@pytest.fixture
def slow_comparison(monkeypatch):
    """Makes each approval wait inside its transaction, so the two really overlap."""
    import app.documents.approval as approval_module

    original = approval_module.comparison

    async def slow(*args, **kwargs):
        await asyncio.sleep(0.3)
        return await original(*args, **kwargs)

    monkeypatch.setattr(approval_module, "comparison", slow)
    return original


@pytest.mark.parametrize(
    "meds",
    [[med("Torasemid", "10 mg")], []],
    # Without medications the comparison hash stays equal: only the row lock protects.
    ids=["with-medication", "without-medication"],
)
async def test_two_parallel_approvals_write_once(db, seeded, slow_comparison, meds):
    doc = review_document(meds=meds)
    async with db.as_principal(NURSE_WB1) as conn:
        _, diff_hash = await slow_comparison(conn, WB1_RESIDENT, "medikationsplan", meds)
    results = await asyncio.gather(
        outcome(approve(db, NURSE_WB1, doc, approval_of(doc, meds, diff_hash))),
        outcome(approve(db, NURSE_WB1, doc, approval_of(doc, meds, diff_hash))),
    )
    assert sorted(results) == ["conflict", "ok"]
    assert admin("select count(*) from public.medication_events") == [(len(meds),)]
    assert admin("select count(*) from public.diagnoses") == [(1,)]


async def test_approval_against_rejection_only_one_wins(db, seeded, slow_comparison):
    doc = review_document()
    async with db.as_principal(NURSE_WB1) as conn:
        _, diff_hash = await slow_comparison(conn, WB1_RESIDENT, "medikationsplan", [])
    results = await asyncio.gather(
        outcome(approve(db, NURSE_WB1, doc, approval_of(doc, [], diff_hash))),
        outcome(reject(db, NURSE_WB1, doc)),
    )
    assert sorted(results) == ["conflict", "ok"]
    (status,) = admin("select status::text from public.documents where id = %s", [doc])[0]
    entries = admin("select count(*) from public.diagnoses")[0][0]
    assert (status, entries) in [("approved", 1), ("rejected", 0)]
