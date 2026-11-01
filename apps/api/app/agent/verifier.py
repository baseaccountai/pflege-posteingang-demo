"""Verify the agent's token (F08-AC3) - the same way for both ways of issuing it.

An agent token is the nurse's identity plus the agent as actor (RFC 8693):

    sub = the nurse, act = {"sub": <agent>}, the nurse's roles     (ADR 0012)

It is accepted only if
  - signature, algorithm, iss, aud, exp and nbf hold (the shared TokenVerifier.decode),
  - act.sub is our agent (AGENT_ID) - nobody else may act through this API,
  - sub is the user of the current session - the agent acts for this nurse only,
  - it was issued at most `max_age` seconds ago. Zitadel issues it for one hour; the
    API keeps it in memory for one task only and refuses it after five minutes.

The principal gets the nurse's role and wards with actor_type = "agent": the agent never
has more rights than the nurse, and RLS and the audit log can tell the two apart.
"""

import dataclasses
import time

from app.auth.claims import NoKnownRole, principal_from_claims
from app.auth.principal import Principal
from app.auth.tokens import LEEWAY_SECONDS, InvalidToken, TokenVerifier

MAX_AGE_SECONDS = 300


class AgentTokenVerifier:
    def __init__(
        self,
        tokens: TokenVerifier,
        agent_id: str,
        roles_claim: str,
        max_age: int = MAX_AGE_SECONDS,
    ):
        self.tokens = tokens  # issuer and keys of the way in use (IdP or the API itself)
        self.agent_id = agent_id
        self.roles_claim = roles_claim
        self.max_age = max_age

    def verify(
        self, token: str, session_sub: str, session_wards: tuple[str, ...] | None = None
    ) -> Principal:
        claims = self.tokens.decode(token)
        act = claims.get("act")
        if not isinstance(act, dict) or act.get("sub") != self.agent_id:
            raise InvalidToken("act does not name our agent")
        if claims.get("sub") != session_sub:
            raise InvalidToken("sub is not the user of the session")
        issued = claims.get("iat")
        now = time.time()
        if not isinstance(issued, int | float) or issued > now + LEEWAY_SECONDS:
            raise InvalidToken("iat missing or in the future")
        if now - issued > self.max_age:
            raise InvalidToken(f"iat more than {self.max_age} s ago")
        try:
            principal = principal_from_claims(claims, self.roles_claim)
        except NoKnownRole as missing:
            raise InvalidToken("no known role in the agent token") from missing
        # The agent never gets more than its nurse: no ward she does not have herself.
        if session_wards is not None and not set(principal.ward_ids) <= set(session_wards):
            raise InvalidToken("agent token has a ward the user does not have")
        return dataclasses.replace(principal, actor_type="agent")
