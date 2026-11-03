"""Builds the Keycloak realm of the fully local mode from infra/demo-users.json (F11-AC15).

    python3 infra/keycloak/build_realm.py     (make keycloak-realm)

Writes infra/keycloak/pflege-realm.json, which Keycloak imports at its start
(`start-dev --import-realm`). A test checks that the committed file is up to date.

Same users, roles and passwords as at Zitadel - public on purpose (F01-AC2). Everything
here is for the local machine only: the client secret is a fixed local value.
"""

import json
from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]
USERS_PATH = INFRA / "demo-users.json"
REALM_PATH = INFRA / "keycloak" / "pflege-realm.json"

REALM = "pflege"
WEB_CLIENT = "pflege-web"
WEB_CLIENT_SECRET = "pflege-web-local-only-secret"  # local stack only, never a real IdP
API_AUDIENCE = "pflege-api"
LOCAL_ORIGIN = "http://localhost:3000"


def load_users(path: Path = USERS_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _local(uris: list[str]) -> list[str]:
    """Only the addresses of the local machine (demo-users.json also lists the public ones)."""
    return [uri for uri in uris if uri.startswith(LOCAL_ORIGIN)]


def _web_client(app: dict) -> dict:
    token_claims = {"access.token.claim": "true", "id.token.claim": "true"}
    return {
        "clientId": WEB_CLIENT,
        "name": app["name"],
        "secret": WEB_CLIENT_SECRET,
        "publicClient": False,  # the Next.js BFF keeps the secret on the server
        "standardFlowEnabled": True,  # code flow ...
        "directAccessGrantsEnabled": False,  # ... and no password grant
        "implicitFlowEnabled": False,
        "serviceAccountsEnabled": False,
        "redirectUris": _local(app["redirect_uris"]),
        "webOrigins": [],
        "attributes": {
            "pkce.code.challenge.method": "S256",  # PKCE required
            "post.logout.redirect.uris": "##".join(_local(app["post_logout_redirect_uris"])),
        },
        "protocolMappers": [
            {
                # Roles as a plain list ["nurse_wb1"] - the API and the BFF read lists as well.
                "name": "roles",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-usermodel-realm-role-mapper",
                "config": {
                    "claim.name": "roles",
                    "multivalued": "true",
                    "jsonType.label": "String",
                    "userinfo.token.claim": "true",
                    **token_claims,
                },
            },
            {
                # The access token is meant for the API (it checks aud, F01-AC6).
                "name": "audience-api",
                "protocol": "openid-connect",
                "protocolMapper": "oidc-audience-mapper",
                "config": {"included.custom.audience": API_AUDIENCE, "access.token.claim": "true"},
            },
        ],
    }


def _user(user: dict) -> dict:
    return {
        "username": user["username"],
        "enabled": True,
        "firstName": user["first_name"],
        "lastName": user["last_name"],
        "email": user["email"],
        "emailVerified": True,
        "credentials": [{"type": "password", "value": user["local_password"], "temporary": False}],
        # Imported users get only these roles; offline_access allows the refresh token the BFF
        # asks for (scope offline_access, as at Zitadel).
        "realmRoles": [*user["roles"], "offline_access"],
    }


def build_realm(config: dict) -> dict:
    # No "clientScopes" key: Keycloak then creates its default scopes, among them "basic"
    # with the claim "sub" (spike 01.11.2026, ADR 0012).
    return {
        "realm": REALM,
        "enabled": True,
        "accessTokenLifespan": 300,
        "roles": {
            "realm": [
                {"name": role["key"], "description": role["display_name"]}
                for role in config["roles"]
            ]
        },
        "clients": [_web_client(config["app"])],
        "users": [_user(user) for user in config["users"]],
    }


def main() -> None:
    realm = build_realm(load_users())
    REALM_PATH.write_text(json.dumps(realm, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"geschrieben: {REALM_PATH}")


if __name__ == "__main__":
    main()
