"""Derive the Principal from verified token claims (F01-AC7).

Only role names count. Zitadel sends the roles claim as an object
{"nurse_wb1": {"<orgId>": "<domain>"}} (we read the keys); other IdPs send a list of names.
Anything else grants nothing. Unknown role names are ignored; without any known role the
caller gets 403.
"""

from app.auth.principal import Principal
from app.auth.tokens import InvalidToken

# IdP role name -> (app_role, wards). The single place where roles become ward rights.
ROLE_MAP: dict[str, tuple[str, tuple[str, ...]]] = {
    "nurse_wb1": ("nurse", ("wb1",)),
    "nurse_wb2": ("nurse", ("wb2",)),
    "pdl": ("pdl", ("wb1", "wb2")),
}
DISPLAY_NAMES = {"wb1": "Pflegekraft WB1", "wb2": "Pflegekraft WB2"}


class NoKnownRole(Exception):
    """Authenticated, but without any role this application knows -> HTTP 403."""


def role_names(value: object) -> list[str]:
    """Role names in token order (object keys or list items); other shapes give none."""
    if isinstance(value, dict | list):
        return [name for name in value if isinstance(name, str)]
    return []


def principal_from_claims(claims: dict, roles_claim: str) -> Principal:
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise InvalidToken("token without sub")

    known = [ROLE_MAP[name] for name in role_names(claims.get(roles_claim)) if name in ROLE_MAP]
    if not known:
        raise NoKnownRole("no known role in token")

    # Several roles: PDL wins, wards are the union (sorted, so claims are deterministic).
    app_role = "pdl" if any(role == "pdl" for role, _ in known) else "nurse"
    ward_ids = tuple(sorted({ward for _, wards in known for ward in wards}))
    if app_role == "pdl":
        display_name = "Pflegedienstleitung"
    else:
        display_name = " / ".join(DISPLAY_NAMES[ward] for ward in ward_ids)
    # The access token carries no name or e-mail (spike S2), so the role label is shown.
    return Principal(sub=sub, app_role=app_role, ward_ids=ward_ids, display_name=display_name)
