"""F08-AC3, AC2a: the API accepts an agent token only if every check holds - signature,
issuer, audience, expiry, subject = the session's user, act.sub = our agent, issued at most
five minutes ago. The test tokens have the shape Zitadel issued in the spike (ADR 0012):
the user's claims plus act = {iss, sub}, valid for one hour."""

import time

import pytest

from app.agent.verifier import AgentTokenVerifier
from app.auth.claims import NoKnownRole
from app.auth.tokens import InvalidToken
from tests.support.oidc import ISSUER, ROLES_CLAIM, claims, rs256, test_verifier

AGENT = "agent-397592785986842667"
NURSE = "user-396838961344968028"


def exchanged(**overrides) -> str:
    """Like the spike's exchanged token: nurse's sub and roles, act = agent, exp - iat = 1 h."""
    now = int(time.time())
    base = {
        "sub": NURSE,
        "act": {"iss": ISSUER, "sub": AGENT},
        "iat": now,
        "exp": now + 3600,
        "client_id": "agent-app",
        "jti": "j-1",
        ROLES_CLAIM: {"nurse_wb1": {"org-1": "org.test"}},
    }
    return rs256(claims(**{**base, **overrides}))


@pytest.fixture
def verifier() -> AgentTokenVerifier:
    return AgentTokenVerifier(test_verifier(), AGENT, ROLES_CLAIM, max_age=300)


def test_an_exchanged_token_gives_the_nurse_as_principal_acting_through_the_agent(verifier):
    principal = verifier.verify(exchanged(), session_sub=NURSE)
    assert (principal.sub, principal.app_role, principal.ward_ids) == (NURSE, "nurse", ("wb1",))
    assert principal.actor_type == "agent"


def test_a_user_token_without_act_is_no_agent_token(verifier):
    with pytest.raises(InvalidToken, match="act"):
        verifier.verify(exchanged(act=None), session_sub=NURSE)


@pytest.mark.parametrize("act", [{"iss": ISSUER, "sub": "other-agent"}, {"iss": ISSUER}, "x"])
def test_only_our_agent_may_act(verifier, act):
    with pytest.raises(InvalidToken, match="act"):
        verifier.verify(exchanged(act=act), session_sub=NURSE)


def test_the_agent_acts_only_for_the_user_of_the_session(verifier):
    with pytest.raises(InvalidToken, match="sub"):
        verifier.verify(exchanged(), session_sub="user-somebody-else")


def test_a_token_issued_more_than_five_minutes_ago_is_refused_though_it_has_not_expired(
    verifier,
):
    now = int(time.time())
    assert verifier.verify(exchanged(iat=now - 290), session_sub=NURSE)
    with pytest.raises(InvalidToken, match="iat"):
        verifier.verify(exchanged(iat=now - 310), session_sub=NURSE)
    with pytest.raises(InvalidToken, match="iat"):
        verifier.verify(exchanged(iat=None), session_sub=NURSE)
    with pytest.raises(InvalidToken, match="iat"):
        verifier.verify(exchanged(iat=now + 120), session_sub=NURSE)  # from the future


@pytest.mark.parametrize(
    "override",
    [
        {"iss": "https://other-idp.example.test"},
        {"aud": ["other-project"]},
        {"exp": int(time.time()) - 60},
    ],
)
def test_issuer_audience_and_expiry_are_checked_as_for_users(verifier, override):
    with pytest.raises(InvalidToken):
        verifier.verify(exchanged(**override), session_sub=NURSE)


def test_a_forged_signature_is_refused(verifier):
    head, body, _ = exchanged().split(".")
    other = rs256(claims(sub="x")).split(".")[2]
    with pytest.raises(InvalidToken):
        verifier.verify(f"{head}.{body}.{other}", session_sub=NURSE)


def test_without_a_known_role_the_agent_gets_nothing(verifier):
    with pytest.raises(NoKnownRole):
        verifier.verify(exchanged(**{ROLES_CLAIM: {"admin": {}}}), session_sub=NURSE)
