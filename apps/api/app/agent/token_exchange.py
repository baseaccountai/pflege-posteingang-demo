"""How the agent gets its own token (F08-AC1, AC2; ADR 0012).

Public demo - token exchange at Zitadel (RFC 8693):
  1. the agent's service user gets its own access token (client credentials),
  2. the API's exchange app trades the nurse's access token for an agent token:
     subject_token = nurse, actor_token = agent  ->  sub = nurse, act.sub = agent.
  Zitadel confirms and logs every such delegation ("User impersonated").

Fallback where the IdP offers no exchange (AGENT_TOKEN_MODE=self_signed): after the nurse's
token has been verified, the API signs a token with the same claims itself (ES256, own
issuer, 5 minutes). Weaker - the API vouches for itself - but checked the same way.

Either way the token stays in the backend and is used for one agent task only.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.agent.verifier import AgentTokenVerifier
from app.auth.tokens import TokenVerifier, fetch_json
from app.config import Settings

SELF_ISSUER = "pflege-posteingang-api/agent"  # never the IdP's issuer: users cannot pass
EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"
JWT_TYPE = "urn:ietf:params:oauth:token-type:jwt"
TIMEOUT_SECONDS = 10


class AgentTokenUnavailable(Exception):
    """No agent token now (IdP down, refused, odd answer) -> the agent does not start."""


class AgentTokenIssuer(Protocol):
    async def issue(self, user_token: str, user_claims: dict) -> str: ...


def _basic(client_id: str, secret: str) -> str:
    # RFC 6749 2.3.1: form-encode id and secret before base64.
    pair = f"{urllib.parse.quote(client_id, safe='')}:{urllib.parse.quote(secret, safe='')}"
    return "Basic " + base64.b64encode(pair.encode()).decode()


class ZitadelExchange:
    def __init__(
        self,
        token_endpoint: str,
        audience: str,
        agent_client: tuple[str, str],
        exchange_client: tuple[str, str],
    ):
        self.token_endpoint = token_endpoint
        self.audience = audience  # the project: the actor token must be meant for it, too
        self.agent_client = agent_client
        self.exchange_client = exchange_client

    async def _token(self, client: httpx.AsyncClient, auth: tuple[str, str], form: dict) -> dict:
        try:
            response = await client.post(
                self.token_endpoint, data=form, headers={"authorization": _basic(*auth)}
            )
        except httpx.HTTPError as error:
            raise AgentTokenUnavailable(f"IdP not reachable: {type(error).__name__}") from None
        if response.status_code != 200:
            # Only the status: the answer may echo what was sent.
            raise AgentTokenUnavailable(f"IdP answered {response.status_code}")
        try:
            answer = response.json()
        except ValueError:
            raise AgentTokenUnavailable("IdP answer is not JSON") from None
        if not isinstance(answer, dict) or not isinstance(answer.get("access_token"), str):
            raise AgentTokenUnavailable("IdP answer without access_token")
        return answer

    async def issue(self, user_token: str, user_claims: dict) -> str:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            actor = await self._token(
                client,
                self.agent_client,
                {
                    "grant_type": "client_credentials",
                    "scope": f"openid urn:zitadel:iam:org:project:id:{self.audience}:aud",
                },
            )
            exchanged = await self._token(
                client,
                self.exchange_client,
                {
                    "grant_type": EXCHANGE,
                    "subject_token": user_token,
                    "subject_token_type": ACCESS_TOKEN,
                    "actor_token": actor["access_token"],
                    "actor_token_type": ACCESS_TOKEN,
                    "requested_token_type": JWT_TYPE,
                },
            )
        if exchanged.get("issued_token_type") != JWT_TYPE:
            raise AgentTokenUnavailable("IdP issued no JWT")  # opaque: the API cannot check it
        return exchanged["access_token"]


class StaticJWKClient(jwt.PyJWKClient):
    """The API's own public key as JWKS: the self-signed token is checked like any other."""

    def __init__(self, jwks: dict):
        # Never fetched (fetch_data below); PyJWT only insists on an http(s) address.
        super().__init__("https://agent-keys.invalid/jwks", cache_jwk_set=False)
        self._jwks = jwks

    def fetch_data(self) -> dict:
        return self._jwks


class SelfSignedIssuer:
    def __init__(
        self, signing_key: str, audience: str, agent_id: str, roles_claim: str, lifetime=300
    ):
        try:
            key = serialization.load_pem_private_key(signing_key.encode(), password=None)
        except (ValueError, TypeError):
            key = None
        if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
            raise ValueError("AGENT_SIGNING_KEY must be an EC P-256 private key (PEM)")
        self.key = key
        self.audience = audience
        self.agent_id = agent_id
        self.roles_claim = roles_claim
        self.lifetime = lifetime
        public = ECAlgorithm.to_jwk(key.public_key(), as_dict=True)
        # kid = RFC 7638 thumbprint: a new key gets a new kid by itself (rotation).
        members = json.dumps(
            {k: public[k] for k in ("crv", "kty", "x", "y")}, separators=(",", ":")
        )
        digest = hashlib.sha256(members.encode()).digest()
        self.kid = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        self.jwks = {"keys": [{**public, "kid": self.kid, "use": "sig", "alg": "ES256"}]}

    async def issue(self, user_token: str, user_claims: dict) -> str:
        """`user_claims` are the verified claims of `user_token` (current_principal)."""
        now = int(time.time())
        payload = {
            "iss": SELF_ISSUER,
            "aud": self.audience,
            "sub": user_claims["sub"],
            "act": {"iss": SELF_ISSUER, "sub": self.agent_id},
            self.roles_claim: user_claims.get(self.roles_claim),
            "iat": now,
            "nbf": now,
            "exp": now + self.lifetime,
            "jti": secrets.token_urlsafe(12),
        }
        return jwt.encode(payload, self.key, algorithm="ES256", headers={"kid": self.kid})

    def verifier(self) -> TokenVerifier:
        return TokenVerifier(SELF_ISSUER, self.audience, StaticJWKClient(self.jwks))


@dataclass(frozen=True)
class AgentTokens:
    issuer: AgentTokenIssuer
    verifier: AgentTokenVerifier


def create_agent_tokens(
    settings: Settings,
    user_verifier: TokenVerifier,
    fetch_json: Callable[[str], dict] = fetch_json,
) -> AgentTokens | None:
    """The way chosen by AGENT_TOKEN_MODE; None if it is not fully configured."""
    if not settings.agent_id:
        return None
    if settings.agent_token_mode == "self_signed":
        if not settings.agent_signing_key:
            return None
        issuer = SelfSignedIssuer(
            settings.agent_signing_key,
            settings.oidc_audience,
            settings.agent_id,
            settings.oidc_roles_claim,
            settings.agent_token_max_seconds,
        )
        tokens = issuer.verifier()
    else:
        secrets_set = (
            settings.agent_client_id,
            settings.agent_client_secret,
            settings.agent_exchange_client_id,
            settings.agent_exchange_client_secret,
        )
        if not all(secrets_set):
            return None
        discovery = fetch_json(
            settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
        )
        issuer = ZitadelExchange(
            discovery["token_endpoint"],
            settings.oidc_audience,
            (settings.agent_client_id, settings.agent_client_secret),
            (settings.agent_exchange_client_id, settings.agent_exchange_client_secret),
        )
        tokens = user_verifier  # the IdP's issuer and keys, exactly as for the nurse
    verifier = AgentTokenVerifier(
        tokens, settings.agent_id, settings.oidc_roles_claim, settings.agent_token_max_seconds
    )
    return AgentTokens(issuer, verifier)
