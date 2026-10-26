"""Zitadel as code: project, roles, OIDC web app and demo users from infra/demo-users.json.

F01-AC16 (users and roles as code, idempotent), F01-AC17 (demo users never get admin
rights), F01-AC18 (passwords are reset every 15 minutes by a GitHub workflow).
Standard library only, so the GitHub workflow needs no installation step.

Developer, once and after changes to demo-users.json (writes client id/secret into .env):
    python3 infra/zitadel/setup.py setup .env [--rotate-secret]
GitHub workflow demo-passwords.yml (env: OIDC_ISSUER, ZITADEL_ADMIN_PAT):
    python3 infra/zitadel/setup.py reset-passwords

The admin token belongs to the service user `pp-setup` (role ORG_OWNER of the demo
organization only). Nothing secret is printed.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol

CONFIG_PATH = Path(__file__).parents[1] / "demo-users.json"
EQUALS = "TEXT_QUERY_METHOD_EQUALS"
# Demo e-mail addresses must not be deliverable (reserved TLD .invalid, RFC 2606).
DEMO_EMAIL = re.compile(r"[a-z0-9.-]+@example\.invalid")


class ConfigError(Exception):
    """demo-users.json or the Zitadel state is not what the demo may run with."""


class Conflict(Exception):
    """Zitadel answered 409: the object already exists."""


class Api(Protocol):
    def call(self, method: str, path: str, body: object = None) -> dict: ...


# --- configuration -------------------------------------------------------------------------


def load_config(path: Path = CONFIG_PATH) -> dict:
    """Read and validate demo-users.json; only the file's own project roles may be granted."""
    config = json.loads(path.read_text())
    role_keys = {role["key"] for role in config["roles"]}
    usernames = [user["username"] for user in config["users"]]
    if len(usernames) != len(set(usernames)):
        raise ConfigError("Benutzernamen in demo-users.json sind nicht eindeutig")
    for user in config["users"]:
        if not user["roles"] or not set(user["roles"]) <= role_keys:
            raise ConfigError(f"{user['username']}: nur Projektrollen {sorted(role_keys)} erlaubt")
        if not DEMO_EMAIL.fullmatch(user["email"]):
            raise ConfigError(f"{user['username']}: E-Mail muss auf @example.invalid enden")
    return config


# --- setup steps ---------------------------------------------------------------------------


def find_id(api: Api, path: str, query: dict) -> str | None:
    result = api.call("POST", path, {"queries": [query]}).get("result", [])
    return result[0]["id"] if result else None


def find_user(api: Api, username: str) -> str | None:
    return find_id(
        api, "/users/_search", {"userNameQuery": {"userName": username, "method": EQUALS}}
    )


def ensure_project(api: Api, name: str) -> str:
    project_id = find_id(api, "/projects/_search", {"nameQuery": {"name": name, "method": EQUALS}})
    if project_id:
        return project_id
    # Role assertion: the roles claim is written into the tokens.
    return api.call("POST", "/projects", {"name": name, "projectRoleAssertion": True})["id"]


def ensure_roles(api: Api, project_id: str, roles: list[dict]) -> None:
    for role in roles:
        try:
            api.call(
                "POST",
                f"/projects/{project_id}/roles",
                {"roleKey": role["key"], "displayName": role["display_name"]},
            )
        except Conflict:
            pass


def app_settings(app: dict) -> dict:
    """OIDC contract from F01-design: code flow, Basic client auth, JWT access tokens."""
    return {
        "redirectUris": app["redirect_uris"],
        "postLogoutRedirectUris": app["post_logout_redirect_uris"],
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"],
        "appType": "OIDC_APP_TYPE_WEB",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
        "accessTokenRoleAssertion": True,
        "idTokenRoleAssertion": True,
        "devMode": True,  # allows the http://localhost redirect (spike S2)
    }


def ensure_app(api: Api, project_id: str, app: dict, rotate_secret: bool) -> tuple[str, str | None]:
    """Returns (client_id, client_secret). The secret is only known when it is (re)generated,
    so a rerun does not break the secret stored in Vercel."""
    base = f"/projects/{project_id}/apps"
    found = api.call(
        "POST",
        f"{base}/_search",
        {"queries": [{"nameQuery": {"name": app["name"], "method": EQUALS}}]},
    )
    existing = found.get("result", [])
    if not existing:
        created = api.call("POST", f"{base}/oidc", {"name": app["name"], **app_settings(app)})
        return created["clientId"], created["clientSecret"]
    app_id, client_id = existing[0]["id"], existing[0]["oidcConfig"]["clientId"]
    api.call("PUT", f"{base}/{app_id}/oidc_config", app_settings(app))
    if not rotate_secret:
        return client_id, None
    secret = api.call("POST", f"{base}/{app_id}/oidc_config/_generate_client_secret")
    return client_id, secret["clientSecret"]


def ensure_user(api: Api, user: dict, project_id: str) -> str:
    user_id = find_user(api, user["username"])
    if user_id:
        api.call(
            "POST",
            f"/users/{user_id}/password",
            {"password": user["password"], "noChangeRequired": True},
        )
    else:
        user_id = api.call(
            "POST",
            "/users/human/_import",
            {
                "userName": user["username"],
                "profile": {"firstName": user["first_name"], "lastName": user["last_name"]},
                "email": {"email": user["email"], "isEmailVerified": True},
                "password": user["password"],
                "passwordChangeRequired": False,
            },
        )["userId"]
    grant = {"projectId": project_id, "roleKeys": user["roles"]}
    try:
        api.call("POST", f"/users/{user_id}/grants", grant)
    except Conflict:
        # Grant exists: set it to exactly the roles from the file.
        grant_id = find_id(api, "/users/grants/_search", {"userIdQuery": {"userId": user_id}})
        api.call("PUT", f"/users/{user_id}/grants/{grant_id}", {"roleKeys": user["roles"]})
    return user_id


def assert_no_admin_membership(api: Api, username: str, user_id: str) -> None:
    """F01-AC17: a demo user with an organization role (ORG_OWNER, ...) stops the setup."""
    found = api.call(
        "POST", "/orgs/me/members/_search", {"queries": [{"userIdQuery": {"userId": user_id}}]}
    )
    if found.get("result"):
        raise ConfigError(f"{username} hat Admin-Rechte in der Organisation – bitte entfernen")


def check_existing_accounts(api: Api, users: list[dict]) -> dict[str, str | None]:
    """Runs before any password is set: an account with admin rights must never get the
    public demo password (F01-AC17). Returns username -> id (None if not created yet)."""
    ids = {user["username"]: find_user(api, user["username"]) for user in users}
    for username, user_id in ids.items():
        if user_id:
            assert_no_admin_membership(api, username, user_id)
    return ids


def setup(api: Api, config: dict, rotate_secret: bool = False) -> dict:
    check_existing_accounts(api, config["users"])
    project_id = ensure_project(api, config["project"])
    ensure_roles(api, project_id, config["roles"])
    client_id, client_secret = ensure_app(api, project_id, config["app"], rotate_secret)
    for user in config["users"]:
        user_id = ensure_user(api, user, project_id)
        assert_no_admin_membership(api, user["username"], user_id)
    for username in config.get("remove_users", []):
        if user_id := find_user(api, username):
            api.call("DELETE", f"/users/{user_id}")
    return {"client_id": client_id, "client_secret": client_secret, "project_id": project_id}


def reset_passwords(api: Api, config: dict) -> None:
    """Only sets the published passwords again (F01-AC18); creates and grants nothing."""
    ids = check_existing_accounts(api, config["users"])
    for user in config["users"]:
        user_id = ids[user["username"]]
        if not user_id:
            raise ConfigError(f"Demo-Nutzer {user['username']} fehlt – erst 'setup' ausführen")
        api.call(
            "POST",
            f"/users/{user_id}/password",
            {"password": user["password"], "noChangeRequired": True},
        )


# --- HTTP client and command line ----------------------------------------------------------


class Management:
    """Zitadel Management API v1 over HTTPS with the service user's personal access token."""

    def __init__(self, issuer: str, pat: str):
        self.base = issuer.rstrip("/") + "/management/v1"
        self.headers = {"Authorization": f"Bearer {pat}", "Content-Type": "application/json"}

    def call(self, method: str, path: str, body: object = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path, data=data, headers=self.headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            text = error.read().decode(errors="replace")
            if error.code == 409:
                raise Conflict(path) from error
            if error.code == 400 and "COMMAND-1m88i" in text:  # "No changes"
                return {}
            raise RuntimeError(f"{method} {path}: HTTP {error.code} {text[:200]}") from error


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.split(" #", 1)[0].strip()
    return values


def upsert_env(path: Path, updates: dict[str, str]) -> None:
    lines, pending = path.read_text().splitlines(), dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    path.write_text("\n".join(lines + [f"{k}={v}" for k, v in pending.items()]) + "\n")


def main(argv: list[str]) -> None:
    command = argv[0] if argv else ""
    if command == "setup" and len(argv) >= 2:
        env_path = Path(argv[1])
        env = read_env(env_path)
        api = Management(env["OIDC_ISSUER"], env["ZITADEL_ADMIN_PAT"])
        result = setup(api, load_config(), rotate_secret="--rotate-secret" in argv)
        updates = {
            "OIDC_CLIENT_ID": result["client_id"],
            "OIDC_AUDIENCE": result["project_id"],
            "ZITADEL_PROJECT_ID": result["project_id"],
        }
        if result["client_secret"]:
            updates["OIDC_CLIENT_SECRET"] = result["client_secret"]
        upsert_env(env_path, updates)
        print(f"Setup fertig. In {env_path} geschrieben: {', '.join(updates)}")
        if result["client_secret"]:
            print("Neues Client-Secret: auch in Vercel (OIDC_CLIENT_SECRET) eintragen.")
    elif command == "reset-passwords":
        api = Management(os.environ["OIDC_ISSUER"], os.environ["ZITADEL_ADMIN_PAT"])
        reset_passwords(api, load_config())
        print("Demo-Passwörter zurückgesetzt.")
    else:
        sys.exit("Aufruf: setup.py setup <.env> [--rotate-secret] | setup.py reset-passwords")


if __name__ == "__main__":
    main(sys.argv[1:])
