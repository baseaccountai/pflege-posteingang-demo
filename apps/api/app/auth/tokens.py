"""Verify OIDC access tokens from the identity provider (F01-AC6, F01-AC19).

The API trusts a token only if
  - its signature checks out against a key from the IdP's JWKS (looked up by `kid`),
  - it uses one of the fixed asymmetric algorithms (never `none`, never HS*),
  - `iss`, `aud`, `exp` and `nbf` match, with 30 s leeway for clock skew.

Nothing here is IdP-specific: issuer and audience come from configuration and the JWKS
address from the issuer's discovery document, so Zitadel and the test OIDC server both work.
"""

import json
import urllib.request
from collections.abc import Callable

import jwt

ALLOWED_ALGORITHMS = ["RS256", "ES256"]
LEEWAY_SECONDS = 30
JWKS_CACHE_SECONDS = 600


class InvalidToken(Exception):
    """Token missing, malformed, forged, expired or meant for someone else -> HTTP 401."""


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def discover_jwks_uri(issuer: str, fetch_json: Callable[[str], dict] = fetch_json) -> str:
    """Read `jwks_uri` from the discovery document; its `issuer` must be ours exactly."""
    document = fetch_json(issuer.rstrip("/") + "/.well-known/openid-configuration")
    if document.get("issuer") != issuer:
        raise InvalidToken("discovery document belongs to a different issuer")
    return document["jwks_uri"]


class TokenVerifier:
    def __init__(self, issuer: str, audience: str, jwks_client: jwt.PyJWKClient):
        self.issuer = issuer
        self.audience = audience
        self.jwks_client = jwks_client

    @classmethod
    def from_issuer(cls, issuer: str, audience: str) -> "TokenVerifier":
        """Production setup: JWKS address via discovery, keys cached for 10 minutes."""
        client = jwt.PyJWKClient(discover_jwks_uri(issuer), lifespan=JWKS_CACHE_SECONDS)
        return cls(issuer, audience, client)

    def verify(self, token: str) -> dict:
        """Return the verified claims or raise InvalidToken (never a partial result)."""
        try:
            # The key is chosen by `kid`; the algorithm list below is fixed, so the token
            # header cannot switch to `none` or to HMAC with the public key as secret.
            key = self.jwks_client.get_signing_key_from_jwt(token).key
            return jwt.decode(
                token,
                key,
                algorithms=ALLOWED_ALGORITHMS,
                issuer=self.issuer,
                audience=self.audience,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except (jwt.PyJWTError, jwt.PyJWKClientError) as error:
            raise InvalidToken(str(error)) from error
