"""F01-AC7: roles claim -> app_role and ward_ids; no known role -> 403.

The roles claim name is configurable (OIDC_ROLES_CLAIM, F01-AC19). Zitadel sends an object
{"nurse_wb1": {"<orgId>": "<domain>"}}; other IdPs (test OIDC server, Keycloak) a list.
"""

import pytest

from app.auth.claims import NoKnownRole, principal_from_claims
from app.auth.tokens import InvalidToken

ZITADEL_CLAIM = "urn:zitadel:iam:org:project:roles"


def zitadel(*roles: str) -> dict:
    return {"sub": "user-1", ZITADEL_CLAIM: {role: {"396807": "org.example"} for role in roles}}


@pytest.mark.parametrize(
    ("role", "app_role", "ward_ids", "display_name"),
    [
        ("nurse_wb1", "nurse", ("wb1",), "Pflegekraft WB1"),
        ("nurse_wb2", "nurse", ("wb2",), "Pflegekraft WB2"),
        ("pdl", "pdl", ("wb1", "wb2"), "Pflegedienstleitung"),
    ],
)
def test_each_demo_role_maps_to_app_role_and_wards(role, app_role, ward_ids, display_name):
    principal = principal_from_claims(zitadel(role), ZITADEL_CLAIM)
    assert principal.sub == "user-1"
    assert principal.app_role == app_role
    assert principal.ward_ids == ward_ids
    assert principal.display_name == display_name
    assert principal.actor_type == "human"


def test_unknown_role_only_is_rejected():
    with pytest.raises(NoKnownRole):
        principal_from_claims(zitadel("admin"), ZITADEL_CLAIM)


def test_missing_roles_claim_is_rejected():
    with pytest.raises(NoKnownRole):
        principal_from_claims({"sub": "user-1"}, ZITADEL_CLAIM)


def test_roles_under_another_claim_name_are_ignored():
    # The configured claim name decides; a same-looking claim elsewhere grants nothing.
    with pytest.raises(NoKnownRole):
        principal_from_claims({"sub": "u", "roles": ["pdl"]}, ZITADEL_CLAIM)


def test_unknown_roles_next_to_known_ones_are_ignored():
    principal = principal_from_claims(zitadel("nurse_wb1", "admin"), ZITADEL_CLAIM)
    assert (principal.app_role, principal.ward_ids) == ("nurse", ("wb1",))


def test_two_nurse_roles_give_the_union_of_wards():
    principal = principal_from_claims(zitadel("nurse_wb2", "nurse_wb1"), ZITADEL_CLAIM)
    assert (principal.app_role, principal.ward_ids) == ("nurse", ("wb1", "wb2"))


@pytest.mark.parametrize("roles", [("nurse_wb1", "pdl"), ("pdl", "nurse_wb1")])
def test_pdl_role_wins_over_nurse_role(roles):
    principal = principal_from_claims({"sub": "u", "roles": list(roles)}, "roles")
    assert (principal.app_role, principal.ward_ids) == ("pdl", ("wb1", "wb2"))


def test_list_form_of_other_idps_is_understood():
    principal = principal_from_claims({"sub": "u", "roles": ["nurse_wb2"]}, "roles")
    assert principal.ward_ids == ("wb2",)


@pytest.mark.parametrize("value", ["nurse_wb1", 42, None, [{"nurse_wb1": 1}]])
def test_unexpected_claim_shapes_grant_nothing(value):
    with pytest.raises(NoKnownRole):
        principal_from_claims({"sub": "u", "roles": value}, "roles")


def test_token_without_sub_is_rejected_as_invalid_token():
    with pytest.raises(InvalidToken):
        principal_from_claims({ZITADEL_CLAIM: {"pdl": {}}}, ZITADEL_CLAIM)
