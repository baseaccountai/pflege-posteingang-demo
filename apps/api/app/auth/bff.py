"""BFF assertion: proof that a request really comes through the Next.js BFF (F01-AC8).

The BFF signs a JWS per API call with the shared secret BFF_API_SECRET:
    {"sid_hash": sha256(session id), "aud": "pflege-api", "iat": now, "exp": now + 60}
The API rejects requests without a valid assertion with 401, even if the user's access
token is valid. A token copied out of the BFF is therefore not enough to call the API.
`sid_hash` identifies the server-side session (e.g. for per-session limits in F02).
"""

import re
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException

from app.config import Settings, get_settings

AUDIENCE = "pflege-api"
MAX_LIFETIME_SECONDS = 60
LEEWAY_SECONDS = 5
MIN_SECRET_BYTES = 32
SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class InvalidBffAssertion(Exception):
    """Assertion missing, forged, expired, too long-lived or malformed -> HTTP 401."""


def verify_bff_assertion(token: str | None, secret: str) -> str:
    """Return the session's `sid_hash` or raise InvalidBffAssertion."""
    if len(secret.encode()) < MIN_SECRET_BYTES:
        # Configuration error, not a client error: fail closed and loudly.
        raise ValueError("BFF_API_SECRET fehlt oder ist kürzer als 32 Bytes")
    if not token:
        raise InvalidBffAssertion("missing")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=AUDIENCE,
            leeway=LEEWAY_SECONDS,
            options={"require": ["sid_hash", "aud", "iat", "exp"]},
        )
    except jwt.PyJWTError as error:
        raise InvalidBffAssertion(str(error)) from error
    if claims["exp"] - claims["iat"] > MAX_LIFETIME_SECONDS:
        raise InvalidBffAssertion("lifetime too long")
    sid_hash = claims["sid_hash"]
    if not isinstance(sid_hash, str) or not SHA256_HEX.fullmatch(sid_hash):
        raise InvalidBffAssertion("malformed sid_hash")
    return sid_hash


def bff_session(
    settings: Annotated[Settings, Depends(get_settings)],
    x_bff_assertion: Annotated[str | None, Header()] = None,
) -> str:
    """FastAPI dependency for business routes: returns sid_hash or answers 401."""
    try:
        return verify_bff_assertion(x_bff_assertion, settings.bff_api_secret)
    except InvalidBffAssertion as error:
        # Same answer for every failure: no hint which check failed.
        raise HTTPException(status_code=401, detail="Nicht angemeldet") from error
