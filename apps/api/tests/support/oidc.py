"""Test IdP: signing keys, an in-memory JWKS and helpers to mint access tokens and
BFF assertions. Nothing here talks to the network."""

import hashlib
import json
import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from app.auth.tokens import TokenVerifier

ISSUER = "https://idp.example.test"
AUDIENCE = "project-123"
ROLES_CLAIM = "urn:zitadel:iam:org:project:roles"
BFF_SECRET = "test-bff-secret-" + "x" * 48  # 64 bytes

RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
EC_KEY = ec.generate_private_key(ec.SECP256R1())
# The API's own key for the agent token in the fallback way (F08-AC2), per test run.
AGENT_SIGNING_KEY = (
    ec.generate_private_key(ec.SECP256R1())
    .private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    .decode()
)


def _jwk(public_key, kid: str, algorithm) -> dict:
    return {**json.loads(algorithm.to_jwk(public_key)), "kid": kid, "use": "sig"}


JWKS = {
    "keys": [
        _jwk(RSA_KEY.public_key(), "rsa-1", RSAAlgorithm),
        _jwk(EC_KEY.public_key(), "ec-1", ECAlgorithm),
    ]
}


class InMemoryJWKClient(jwt.PyJWKClient):
    """PyJWKClient whose JWKS comes from memory; key lookup by `kid` stays the real code."""

    def __init__(self, jwks: dict = JWKS):
        super().__init__(f"{ISSUER}/keys", cache_jwk_set=False)
        self._jwks = jwks

    def fetch_data(self) -> dict:
        return self._jwks


def test_verifier() -> TokenVerifier:
    return TokenVerifier(issuer=ISSUER, audience=AUDIENCE, jwks_client=InMemoryJWKClient())


test_verifier.__test__ = False  # helper, not a test


def claims(**overrides) -> dict:
    now = int(time.time())
    base = {
        "iss": ISSUER,
        "aud": [AUDIENCE, "client-1"],
        "sub": "user-1",
        "iat": now,
        "nbf": now,
        "exp": now + 300,
    }
    base.update(overrides)
    return {key: value for key, value in base.items() if value is not None}


def rs256(payload: dict, kid: str = "rsa-1") -> str:
    return jwt.encode(payload, RSA_KEY, algorithm="RS256", headers={"kid": kid})


def access_token(sub: str, *roles: str) -> str:
    """Zitadel-shaped access token with project roles."""
    return rs256(claims(sub=sub, **{ROLES_CLAIM: {role: {"org-1": "org.test"} for role in roles}}))


def bff_assertion(session_id: str = "session-1") -> str:
    now = int(time.time())
    sid_hash = hashlib.sha256(session_id.encode()).hexdigest()
    payload = {"sid_hash": sid_hash, "aud": "pflege-api", "iat": now, "exp": now + 60}
    return jwt.encode(payload, BFF_SECRET, algorithm="HS256")
