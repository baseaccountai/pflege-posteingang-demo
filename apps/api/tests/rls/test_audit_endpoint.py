"""F12-AC6, AC7: GET /audit - the log for the PDL, newest first, 50 per page, filters
"agent only" and "blocked only". Nurses get 403; the database (RLS) would show them
nothing anyway."""

from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

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

pytestmark = pytest.mark.db


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def event(action="question", outcome="ok", actor_type="human", ward="wb1", **extra) -> int:
    agent = actor_type == "agent"
    return admin(
        "insert into public.audit_events (ward_id, action, outcome, actor_type, actor_sub,"
        " actor_name, on_behalf_of_name, model, resident_id, details)"
        " values (%s, %s, %s, %s, 'u-wb1', %s, %s, %s, %s, %s) returning id",
        [
            ward,
            action,
            outcome,
            actor_type,
            "KI-Agent" if agent else "Pflegekraft WB1",
            "Pflegekraft WB1" if agent else None,
            extra.get("model"),
            extra.get("resident_id"),
            Jsonb(extra.get("details", {})),
        ],
    )[0][0]


@pytest.fixture
def api(seeded: None) -> Iterator[TestClient]:
    admin("truncate public.audit_events")
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
    )
    with TestClient(create_app(settings, verifier=test_verifier())) as client:
        yield client
    admin("truncate public.audit_events")


def get(api, role="pdl", **params):
    headers = {
        "Authorization": f"Bearer {access_token(f'u-{role}', role)}",
        "X-Bff-Assertion": bff_assertion(),
    }
    return api.get("/audit", headers=headers, params=params)


def test_the_pdl_reads_the_events_newest_first_with_resident_names(api):
    first = event(model="mistral-small-latest", resident_id=WB1_RESIDENT)
    second = event("blocked", "blocked", "agent", details={"layer": "pattern", "rule_id": "r1"})
    response = get(api)
    assert response.status_code == 200
    body = response.json()
    assert [e["id"] for e in body["events"]] == [second, first]
    assert body["next_before"] is None
    newest, oldest = body["events"]
    assert newest | {"at": None} == {
        "id": second,
        "at": None,
        "ward_id": "wb1",
        "action": "blocked",
        "outcome": "blocked",
        "actor_type": "agent",
        "actor_name": "KI-Agent",
        "on_behalf_of_name": "Pflegekraft WB1",
        "model": None,
        "document_id": None,
        "resident_id": None,
        "resident_name": None,
        "details": {"layer": "pattern", "rule_id": "r1"},
    }
    assert newest["at"]  # ISO timestamp
    # The name comes from the residents table when reading (RLS), not from the log (F12-AC3).
    assert (oldest["resident_name"], oldest["model"]) == (
        "Hr. Muster-Bauer",
        "mistral-small-latest",
    )


def test_pages_of_fifty_continue_below_the_smallest_shown_number(api):
    ids = [event() for _ in range(55)]
    page = get(api).json()
    assert [e["id"] for e in page["events"]] == ids[:4:-1]
    assert page["next_before"] == ids[5]
    rest = get(api, before=page["next_before"]).json()
    assert [e["id"] for e in rest["events"]] == ids[4::-1]
    assert rest["next_before"] is None


def test_filters_agent_only_and_blocked_only(api):
    human = event()
    agent = event(actor_type="agent")
    blocked = event("blocked", "blocked")
    both = event("blocked", "blocked", "agent")
    ids = lambda **f: [e["id"] for e in get(api, **f).json()["events"]]  # noqa: E731
    assert ids(agent_only="true") == [both, agent]
    assert ids(blocked_only="true") == [both, blocked]
    assert ids(agent_only="true", blocked_only="true") == [both]
    assert human in ids()


def test_events_without_a_ward_are_shown_to_the_pdl(api):
    pdl_question = event(ward=None)
    assert [e["id"] for e in get(api).json()["events"]] == [pdl_question]


@pytest.mark.parametrize("role", ["nurse_wb1", "nurse_wb2"])
def test_nurses_get_no_access(api, role):
    event()
    response = get(api, role)
    assert response.status_code == 403
    assert response.json()["error_code"] == "pdl_only"


def test_a_bad_cursor_is_rejected(api):
    assert get(api, before="abc").status_code == 422
