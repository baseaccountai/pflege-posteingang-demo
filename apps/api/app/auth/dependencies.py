"""FastAPI dependencies: who is calling, and a database transaction on their behalf.

Order of checks for every business route:
  1. BFF assertion (request came through the BFF)  -> else 401
  2. access token via JWKS                          -> else 401
  3. known role in the token                        -> else 403
All 401 answers look the same, so a caller cannot tell which check failed.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from psycopg import AsyncConnection

from app.auth.bff import bff_session
from app.auth.claims import NoKnownRole, principal_from_claims
from app.auth.principal import Principal
from app.auth.tokens import InvalidToken

UNAUTHENTICATED = HTTPException(status_code=401, detail="Nicht angemeldet")


@dataclass(frozen=True)
class VerifiedCaller:
    """The caller plus the verified token: only the agent route needs the token itself, to
    exchange it for the agent's token (F08). It is never stored or logged."""

    principal: Principal
    token: str
    claims: dict


def current_caller(
    request: Request,
    _sid_hash: Annotated[str, Depends(bff_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> VerifiedCaller:
    verifier = request.app.state.verifier
    if verifier is None:
        raise HTTPException(status_code=503, detail="Anmeldung nicht konfiguriert")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UNAUTHENTICATED
    try:
        claims = verifier.verify(token)
        principal = principal_from_claims(claims, request.app.state.settings.oidc_roles_claim)
    except InvalidToken as error:
        raise UNAUTHENTICATED from error
    except NoKnownRole as error:
        raise HTTPException(status_code=403, detail="Kein Zugriff") from error
    return VerifiedCaller(principal, token, claims)


def current_principal(caller: Annotated[VerifiedCaller, Depends(current_caller)]) -> Principal:
    return caller.principal


async def principal_db(
    request: Request, principal: Annotated[Principal, Depends(current_principal)]
) -> AsyncIterator[AsyncConnection]:
    """Connection inside one transaction as `authenticated` with the caller's claims (RLS)."""
    database = request.app.state.database
    if database is None:
        raise HTTPException(status_code=503, detail="Datenbank nicht konfiguriert")
    async with database.as_principal(principal) as conn:
        yield conn
