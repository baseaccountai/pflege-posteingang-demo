"""F11-AC15: the Keycloak realm of the fully local mode, built from infra/demo-users.json.

The same users, roles and passwords as at Zitadel (public on purpose, F01-AC2), the roles
as a plain list in the claim "roles", login only with code flow + PKCE. The committed
realm file must be exactly what the generator builds (run `make keycloak-realm`).
"""

import json

from keycloak.build_realm import API_AUDIENCE, REALM_PATH, WEB_CLIENT, build_realm, load_users

CONFIG = load_users()
REALM = build_realm(CONFIG)


def web_client() -> dict:
    (client,) = [c for c in REALM["clients"] if c["clientId"] == WEB_CLIENT]
    return client


def mapper(kind: str) -> dict:
    (found,) = [m for m in web_client()["protocolMappers"] if m["protocolMapper"] == kind]
    return found


def test_the_committed_realm_is_the_generated_one():
    assert json.loads(REALM_PATH.read_text(encoding="utf-8")) == REALM


def test_exactly_the_three_roles_of_the_demo():
    assert {r["name"] for r in REALM["roles"]["realm"]} == {"nurse_wb1", "nurse_wb2", "pdl"}


def test_the_demo_users_with_their_public_passwords_and_roles():
    users = {u["username"]: u for u in REALM["users"]}
    assert set(users) == {"pflege-wb1", "pflege-wb2", "pdl"}
    for wanted in CONFIG["users"]:
        user = users[wanted["username"]]
        assert user["realmRoles"] == wanted["roles"]
        assert user["credentials"] == [
            {"type": "password", "value": wanted["password"], "temporary": False}
        ]
        assert user["enabled"] and user["emailVerified"]


def test_login_only_with_code_flow_and_pkce():
    client = web_client()
    assert client["publicClient"] is False  # the BFF holds the secret
    assert client["standardFlowEnabled"] is True
    assert client["directAccessGrantsEnabled"] is False  # no password grant
    assert client["implicitFlowEnabled"] is False
    assert client["serviceAccountsEnabled"] is False
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"
    assert client["redirectUris"] == ["http://localhost:3000/auth/callback"]
    assert client["attributes"]["post.logout.redirect.uris"] == "http://localhost:3000/"


def test_the_roles_are_a_list_in_the_claim_roles_of_both_tokens():
    config = mapper("oidc-usermodel-realm-role-mapper")["config"]
    assert config["claim.name"] == "roles"
    assert config["multivalued"] == "true"
    assert config["id.token.claim"] == config["access.token.claim"] == "true"


def test_the_access_token_is_for_the_api():
    config = mapper("oidc-audience-mapper")["config"]
    assert config["included.custom.audience"] == API_AUDIENCE
    assert config["access.token.claim"] == "true"


def test_the_default_client_scopes_stay():
    # Spike 01.11.2026 (ADR 0012): an empty list drops the scope "basic" - and with it "sub".
    assert "clientScopes" not in REALM
