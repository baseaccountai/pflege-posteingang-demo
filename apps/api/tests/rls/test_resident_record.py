"""F04: resident list with counters, the record with provenance and "follow-up done" -
through the whole API stack against the local database (RLS as the caller)."""

from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

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
