"""F08-AC1, AC2: how the agent gets its token - by token exchange at the identity provider
(public demo, ADR 0012) or, where the IdP offers none, signed by the API itself. Both
tokens pass the same AgentTokenVerifier. The IdP is faked with respx; no network."""

import base64
import urllib.parse

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.agent.token_exchange import (
    SELF_ISSUER,
    AgentTokenUnavailable,
    SelfSignedIssuer,
    ZitadelExchange,
    create_agent_tokens,
)
from app.agent.verifier import AgentTokenVerifier
from app.auth.tokens import InvalidToken
from app.config import Settings
from tests.support.oidc import AUDIENCE, ISSUER, ROLES_CLAIM, access_token, test_verifier

pytestmark = pytest.mark.anyio
TOKEN_URL = f"{ISSUER}/oauth/v2/token"
AGENT = "agent-1"
EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
JWT_TYPE = "urn:ietf:params:oauth:token-type:jwt"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def nurse() -> tuple[str, dict]:
    token = access_token("user-1", "nurse_wb1")
    return token, test_verifier().verify(token)


def basic(client_id: str, secret: str) -> str:
    pair = f"{urllib.parse.quote(client_id, safe='')}:{urllib.parse.quote(secret, safe='')}"
    return "Basic " + base64.b64encode(pair.encode()).decode()


# --- self-signed (AC2) ------------------------------------------------------------------


async def test_the_api_signs_an_agent_token_with_the_nurses_claims_for_five_minutes():
    issuer = SelfSignedIssuer(pem(), AUDIENCE, AGENT, ROLES_CLAIM)
    token, user_claims = nurse()
    agent_token = await issuer.issue(token, user_claims)
    header = jwt.get_unverified_header(agent_token)
    body = jwt.decode(agent_token, options={"verify_signature": False})
    assert header["alg"] == "ES256" and header["kid"] == issuer.kid
    assert body["iss"] == SELF_ISSUER and body["aud"] == AUDIENCE
    assert body["sub"] == "user-1" and body["act"] == {"iss": SELF_ISSUER, "sub": AGENT}
    assert body[ROLES_CLAIM] == user_claims[ROLES_CLAIM]
    assert body["exp"] - body["iat"] == 300


async def test_both_ways_give_the_same_principal():
    issuer = SelfSignedIssuer(pem(), AUDIENCE, AGENT, ROLES_CLAIM)
    token, user_claims = nurse()
    verifier = AgentTokenVerifier(issuer.verifier(), AGENT, ROLES_CLAIM)
    principal = verifier.verify(await issuer.issue(token, user_claims), session_sub="user-1")
    assert (principal.app_role, principal.ward_ids, principal.actor_type) == (
        "nurse",
        ("wb1",),
        "agent",
    )


async def test_a_self_signed_token_is_no_user_token_and_another_key_cannot_forge_one():
    issuer = SelfSignedIssuer(pem(), AUDIENCE, AGENT, ROLES_CLAIM)
    token, user_claims = nurse()
    agent_token = await issuer.issue(token, user_claims)
    with pytest.raises(InvalidToken):
        test_verifier().verify(agent_token)  # wrong issuer for users, and it carries act
    forger = SelfSignedIssuer(pem(), AUDIENCE, AGENT, ROLES_CLAIM)
    forged = await forger.issue(token, user_claims)
    with pytest.raises(InvalidToken):
        AgentTokenVerifier(issuer.verifier(), AGENT, ROLES_CLAIM).verify(forged, "user-1")


# --- token exchange at Zitadel (AC1) ----------------------------------------------------


def zitadel() -> ZitadelExchange:
    return ZitadelExchange(TOKEN_URL, AUDIENCE, ("agent-client", "s1"), ("exchange-app", "s2"))


@respx.mock
async def test_the_nurses_token_is_exchanged_with_the_agents_own_token_as_actor():
    seen: list[tuple[str, dict]] = []

    def idp(request: httpx.Request) -> httpx.Response:
        form = dict(urllib.parse.parse_qsl(request.content.decode()))
        seen.append((request.headers["authorization"], form))
        if form["grant_type"] == "client_credentials":
            return httpx.Response(200, json={"access_token": "actor-token"})
        return httpx.Response(
            200, json={"access_token": "agent-token", "issued_token_type": JWT_TYPE}
        )

    respx.post(TOKEN_URL).mock(side_effect=idp)
    token, user_claims = nurse()
    assert await zitadel().issue(token, user_claims) == "agent-token"

    (actor_auth, actor_form), (exchange_auth, exchange_form) = seen
    assert actor_auth == basic("agent-client", "s1")
    assert actor_form["scope"] == f"openid urn:zitadel:iam:org:project:id:{AUDIENCE}:aud"
    assert exchange_auth == basic("exchange-app", "s2")
    assert exchange_form == {
        "grant_type": EXCHANGE,
        "subject_token": token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "actor_token": "actor-token",
        "actor_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "requested_token_type": JWT_TYPE,
    }


@respx.mock
@pytest.mark.parametrize(
    "answers",
    [
        [httpx.Response(401, json={"error": "invalid_client"})],
        [httpx.Response(200, json={"access_token": "a"}), httpx.Response(400, json={})],
        [httpx.Response(200, json={"access_token": "a"}), httpx.Response(200, json={})],
        [  # an opaque token instead of the JWT the API can check
            httpx.Response(200, json={"access_token": "a"}),
            httpx.Response(200, json={"access_token": "b", "issued_token_type": "x"}),
        ],
        [httpx.ConnectError("down")],
    ],
)
async def test_a_failed_exchange_is_unavailable_and_names_no_token(answers):
    respx.post(TOKEN_URL).mock(side_effect=answers)
    token, user_claims = nurse()
    with pytest.raises(AgentTokenUnavailable) as caught:
        await zitadel().issue(token, user_claims)
    assert token not in str(caught.value) and "s1" not in str(caught.value)


# --- configuration (AGENT_TOKEN_MODE) ---------------------------------------------------


def settings(**values) -> Settings:
    return Settings(
        oidc_issuer=ISSUER, oidc_audience=AUDIENCE, oidc_roles_claim=ROLES_CLAIM, **values
    )


def test_exchange_mode_finds_the_token_endpoint_by_discovery():
    def discovery(url: str) -> dict:
        assert url == f"{ISSUER}/.well-known/openid-configuration"
        return {"issuer": ISSUER, "token_endpoint": TOKEN_URL}

    configured = settings(
        agent_id=AGENT,
        agent_client_id="agent-client",
        agent_client_secret="s1",
        agent_exchange_client_id="exchange-app",
        agent_exchange_client_secret="s2",
    )
    agent = create_agent_tokens(configured, test_verifier(), fetch_json=discovery)
    assert isinstance(agent.issuer, ZitadelExchange)
    assert agent.issuer.token_endpoint == TOKEN_URL
    assert agent.verifier.tokens.issuer == ISSUER  # the IdP's keys, as for users
    assert agent.verifier.max_age == 300


async def test_self_signed_mode_issues_and_verifies_with_the_apis_key():
    configured = settings(agent_token_mode="self_signed", agent_id=AGENT, agent_signing_key=pem())
    agent = create_agent_tokens(configured, test_verifier())
    token, user_claims = nurse()
    principal = agent.verifier.verify(await agent.issuer.issue(token, user_claims), "user-1")
    assert principal.actor_type == "agent"


@pytest.mark.parametrize(
    "values",
    [
        {},  # no agent configured at all
        {"agent_id": AGENT, "agent_client_id": "c"},  # exchange without secrets
        {"agent_token_mode": "self_signed", "agent_id": AGENT},  # no signing key
    ],
)
def test_without_complete_configuration_there_is_no_agent(values):
    assert create_agent_tokens(settings(**values), test_verifier()) is None


def test_the_signing_key_must_be_an_ec_p256_key():
    with pytest.raises(ValueError, match="P-256"):
        SelfSignedIssuer("not a key", AUDIENCE, AGENT, ROLES_CLAIM)
