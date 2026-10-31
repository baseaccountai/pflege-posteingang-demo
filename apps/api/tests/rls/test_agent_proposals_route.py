"""F08-AC5, AC6: confirming and dismissing a proposal through the API.

Confirming takes two different rights: first the nurse herself sets the proposal to
"confirmed" (an agent token cannot), then the agent - with a fresh agent token - writes the
follow-up, which RLS allows only for that confirmed proposal. Only once, only by the nurse
it was made for, only before it expires.
"""

import uuid

import pytest

from app.providers.llm.fake import FakeLlm
from tests.rls.conftest import WB1_RESIDENT
from tests.rls.test_agent_route import admin, client, ward  # noqa: F401 (fixture)
from tests.rls.test_record_rls import record  # noqa: F401 (fixture of ward)
from tests.support.oidc import access_token, bff_assertion

pytestmark = pytest.mark.db

NURSE = "u-nurse_wb1"


def proposal(created_for: str = NURSE, expired: bool = False) -> str:
    """An open proposal of the agent for the nurse (written with admin rights)."""
    expires = "now() - interval '1 second'" if expired else "now() + interval '15 minutes'"
    (proposal_id,) = admin(
        "insert into public.agent_proposals (ward_id, resident_id, title, due_date,"
        f" created_for, expires_at) values ('wb1', %s, 'Blutdruck messen', current_date + 2,"
        f" %s, {expires}) returning id::text",
        [WB1_RESIDENT, created_for],
    )[0]
    return proposal_id


def post(path: str, sub: str = NURSE, with_agent: bool = True):
    headers = {
        "Authorization": f"Bearer {access_token(sub, 'nurse_wb1')}",
        "X-Bff-Assertion": bff_assertion(),
    }
    with client(FakeLlm(), with_agent) as api:
        return api.post(path, headers=headers)


def status_of(proposal_id: str) -> str:
    return admin("select status from public.agent_proposals where id = %s", [proposal_id])[0][0]


def test_confirming_writes_the_follow_up_as_the_agent_confirmed_by_the_nurse(ward):  # noqa: F811
    pid = proposal()
    response = post(f"/agent/proposals/{pid}/confirm")
    assert response.status_code == 200
    follow_up = response.json()["follow_up_id"]
    assert admin(
        "select title, due_date = current_date + 2, actor_type, created_by, confirmed_by,"
        " proposal_id::text from public.follow_ups where id = %s",
        [follow_up],
    ) == [("Blutdruck messen", True, "agent", NURSE, NURSE, pid)]
    assert status_of(pid) == "confirmed"


def test_a_proposal_is_confirmed_only_once(ward):  # noqa: F811
    pid = proposal()
    assert post(f"/agent/proposals/{pid}/confirm").status_code == 200
    again = post(f"/agent/proposals/{pid}/confirm")
    assert again.status_code == 409
    assert again.json()["error_code"] == "proposal_decided"
    assert admin("select count(*) from public.follow_ups where proposal_id = %s", [pid]) == [(1,)]


def test_a_confirmed_proposal_without_follow_up_can_be_saved_again(ward):  # noqa: F811
    # Step 2 happened (by the nurse), step 3 failed: confirming again only does step 3.
    pid = proposal()
    admin("update public.agent_proposals set status = 'confirmed' where id = %s", [pid])
    response = post(f"/agent/proposals/{pid}/confirm")
    assert response.status_code == 200
    assert admin("select count(*) from public.follow_ups where proposal_id = %s", [pid]) == [(1,)]


def test_dismissing_writes_nothing_into_the_record(ward):  # noqa: F811
    pid = proposal()
    response = post(f"/agent/proposals/{pid}/dismiss")
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert status_of(pid) == "dismissed"
    assert admin("select count(*) from public.follow_ups where proposal_id = %s", [pid]) == [(0,)]
    for action in ("confirm", "dismiss"):
        decided = post(f"/agent/proposals/{pid}/{action}")
        assert decided.status_code == 409
        assert decided.json()["error_code"] == "proposal_decided"


@pytest.mark.parametrize("action", ["confirm", "dismiss"])
def test_an_expired_proposal_cannot_be_decided(ward, action):  # noqa: F811
    pid = proposal(expired=True)
    response = post(f"/agent/proposals/{pid}/{action}")
    assert response.status_code == 409
    assert response.json()["error_code"] == "proposal_expired"
    assert status_of(pid) == "open"


@pytest.mark.parametrize("action", ["confirm", "dismiss"])
def test_another_persons_unknown_and_malformed_proposals_do_not_exist(ward, action):  # noqa: F811
    colleagues = proposal(created_for="u-colleague")
    for pid in (colleagues, str(uuid.uuid4()), "kein-uuid"):
        assert post(f"/agent/proposals/{pid}/{action}").status_code == 404
    assert status_of(colleagues) == "open"


def test_without_a_configured_agent_nothing_is_confirmed(ward):  # noqa: F811
    pid = proposal()
    response = post(f"/agent/proposals/{pid}/confirm", with_agent=False)
    assert response.status_code == 503
    assert status_of(pid) == "open"
