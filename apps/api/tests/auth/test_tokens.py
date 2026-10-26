"""F01-AC6, F01-AC19: access tokens are verified via JWKS with a fixed algorithm list.

Keys are generated per test run; the JWKS is served from memory instead of the network,
but key lookup by `kid` runs through the real PyJWKClient code path.
"""

import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from jwt.algorithms import ECAlgorithm, RSAAlgorithm

from app.auth.tokens import InvalidToken, TokenVerifier, discover_jwks_uri

ISSUER = "https://idp.example.test"
AUDIENCE = "project-123"

RSA_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
EC_KEY = ec.generate_private_key(ec.SECP256R1())


def jwk(public_key, kid: str, algorithm) -> dict:
    data = json.loads(algorithm.to_jwk(public_key))
    return {**data, "kid": kid, "use": "sig"}


JWKS = {
    "keys": [
        jwk(RSA_KEY.public_key(), "rsa-1", RSAAlgorithm),
        jwk(EC_KEY.public_key(), "ec-1", ECAlgorithm),
    ]
}


class InMemoryJWKClient(jwt.PyJWKClient):
    """PyJWKClient whose JWKS comes from memory instead of an HTTP request."""

    def __init__(self, jwks: dict):
        super().__init__("https://idp.example.test/keys", cache_jwk_set=False)
        self._jwks = jwks

    def fetch_data(self) -> dict:
        return self._jwks


@pytest.fixture
def verifier() -> TokenVerifier:
    return TokenVerifier(issuer=ISSUER, audience=AUDIENCE, jwks_client=InMemoryJWKClient(JWKS))


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


def test_valid_rs256_token_returns_claims(verifier):
    assert verifier.verify(rs256(claims()))["sub"] == "user-1"


def test_valid_es256_token_is_accepted(verifier):
    token = jwt.encode(claims(), EC_KEY, algorithm="ES256", headers={"kid": "ec-1"})
    assert verifier.verify(token)["sub"] == "user-1"


def test_expired_token_is_rejected(verifier):
    now = int(time.time())
    with pytest.raises(InvalidToken):
        verifier.verify(rs256(claims(iat=now - 600, nbf=now - 600, exp=now - 60)))


def test_expiry_within_30s_leeway_is_accepted(verifier):
    now = int(time.time())
    assert verifier.verify(rs256(claims(iat=now - 600, nbf=now - 600, exp=now - 10)))


def test_token_not_yet_valid_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify(rs256(claims(nbf=int(time.time()) + 120)))


def test_wrong_issuer_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify(rs256(claims(iss="https://evil.example.test")))


def test_wrong_audience_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify(rs256(claims(aud=["other-project"])))


def test_token_without_exp_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify(rs256(claims(exp=None)))


def test_alg_none_is_rejected(verifier):
    token = jwt.encode(claims(), None, algorithm="none", headers={"kid": "rsa-1"})
    with pytest.raises(InvalidToken):
        verifier.verify(token)


def test_hs256_signed_with_public_key_is_rejected(verifier):
    # Algorithm confusion: attacker uses the published RSA public key as HMAC secret.
    public_pem = RSA_KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    header = {"alg": "HS256", "typ": "JWT", "kid": "rsa-1"}
    segments = [
        jwt.utils.base64url_encode(json.dumps(part).encode()) for part in (header, claims())
    ]
    signing_input = b".".join(segments)
    signature = jwt.utils.base64url_encode(
        hmac.new(public_pem, signing_input, hashlib.sha256).digest()
    )
    with pytest.raises(InvalidToken):
        verifier.verify((signing_input + b"." + signature).decode())


def test_unknown_kid_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify(rs256(claims(), kid="unknown"))


def test_garbage_is_rejected(verifier):
    with pytest.raises(InvalidToken):
        verifier.verify("not-a-jwt")


def test_jwks_uri_comes_from_discovery():
    # F01-AC19: no IdP-specific paths in code; Zitadel and the mock server differ.
    documents = {
        f"{ISSUER}/.well-known/openid-configuration": {"issuer": ISSUER, "jwks_uri": f"{ISSUER}/k"}
    }
    assert discover_jwks_uri(ISSUER, fetch_json=documents.__getitem__) == f"{ISSUER}/k"


def test_discovery_with_other_issuer_is_rejected():
    documents = {
        f"{ISSUER}/.well-known/openid-configuration": {
            "issuer": "https://evil.test",
            "jwks_uri": "x",
        }
    }
    with pytest.raises(InvalidToken):
        discover_jwks_uri(ISSUER, fetch_json=documents.__getitem__)
