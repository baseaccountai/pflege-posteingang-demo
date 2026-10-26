"""Spike S2 + S4 (F01, Task 2): does Zitadel give us what the OIDC contract in F01-design needs?

Throwaway draft. The tested, idempotent setup script follows in F01 Task 7 (infra/zitadel/setup.py).
Run by the developer in their own terminal, never in CI:

    cd apps/api && uv run python -m scripts.zitadel_spike setup ../../.env
    cd apps/api && uv run python -m scripts.zitadel_spike login ../../.env

setup  Creates (or reuses) project, roles, web app and one test user `spike-wb1` via the
       Management API (ZITADEL_ADMIN_PAT). Writes OIDC_CLIENT_ID, OIDC_CLIENT_SECRET,
       OIDC_AUDIENCE and ZITADEL_PROJECT_ID into the .env file. Prints only the test
       user's login name and throwaway password (no admin rights, deleted in Task 7).
login  Runs a real Authorization Code + PKCE login through the browser, then checks token
       type, claims, signature (JWKS), revocation and end_session without id_token_hint.
       Prints claims and results, never a token.
"""

import base64
import hashlib
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import jwt

from scripts.provision_db_roles import read_env, upsert_env

PROJECT_NAME = "pflege-posteingang"
APP_NAME = "pflege-posteingang-web"
ROLES = {
    "nurse_wb1": "Pflegekraft WB1",
    "nurse_wb2": "Pflegekraft WB2",
    "pdl": "Pflegedienstleitung",
}
SPIKE_USER = "spike-wb1"
REDIRECT_URIS = [
    "https://pflege-posteingang-demo.vercel.app/auth/callback",
    "http://localhost:3000/auth/callback",
]
POST_LOGOUT_URIS = ["https://pflege-posteingang-demo.vercel.app/", "http://localhost:3000/"]
LOCAL_REDIRECT = "http://localhost:3000/auth/callback"
LOCAL_POST_LOGOUT = "http://localhost:3000/"
ROLES_CLAIM = "urn:zitadel:iam:org:project:roles"


# --- small HTTP helper (stdlib only, so the spike needs no extra client library) ---------


class HttpError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {body[:300]}")
        self.status = status
        self.body = body


def http(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: object = None,
    form: dict[str, str] | None = None,
) -> tuple[int, dict, dict]:
    """Returns (status, response headers, parsed JSON body or {}). Does not follow redirects."""
    data = None
    headers = dict(headers or {})
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener.open(request, timeout=20) as response:
            status, resp_headers, raw = (
                response.status,
                lower_keys(response.headers),
                response.read(),
            )
    except urllib.error.HTTPError as error:
        status, resp_headers, raw = error.code, lower_keys(error.headers), error.read()
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        body = {"_raw": raw.decode(errors="replace")[:300]}
    return status, resp_headers, body


def lower_keys(headers) -> dict[str, str]:
    """HTTP header names are case-insensitive; Zitadel sends them in lower case."""
    return {key.lower(): value for key, value in headers.items()}


class Management:
    """Minimal client for the Zitadel Management API v1 (organization of the PAT's user)."""

    def __init__(self, issuer: str, pat: str):
        self.base = issuer.rstrip("/") + "/management/v1"
        self.auth = {"Authorization": f"Bearer {pat}"}

    def call(
        self, method: str, path: str, body: object = None, *, ok_conflict: bool = False
    ) -> dict:
        status, _, data = http(method, self.base + path, headers=self.auth, json_body=body)
        if status == 409 and ok_conflict:
            return {}
        # Zitadel answers 400 "No changes" (COMMAND-1m88i) when an update changes nothing.
        if status == 400 and "COMMAND-1m88i" in json.dumps(data):
            return {}
        if status >= 300:
            raise HttpError(status, json.dumps(data))
        return data


# --- setup ---------------------------------------------------------------------------------


def find_one(api: Management, path: str, query: dict) -> dict | None:
    result = api.call("POST", path, {"queries": [query]}).get("result", [])
    return result[0] if result else None


def setup(env_path: Path) -> None:
    env = read_env(env_path)
    issuer, pat = env.get("OIDC_ISSUER"), env.get("ZITADEL_ADMIN_PAT")
    if not issuer or not pat:
        sys.exit("OIDC_ISSUER und ZITADEL_ADMIN_PAT müssen in der .env-Datei stehen.")
    api = Management(issuer, pat)
    org_id = api.call("GET", "/orgs/me")["org"]["id"]
    print(f"Organisation: {org_id}")

    # Project: role assertion on, so the roles claim lands in the tokens.
    eq = "TEXT_QUERY_METHOD_EQUALS"
    project = find_one(
        api, "/projects/_search", {"nameQuery": {"name": PROJECT_NAME, "method": eq}}
    )
    project_id = (
        project["id"]
        if project
        else api.call("POST", "/projects", {"name": PROJECT_NAME, "projectRoleAssertion": True})[
            "id"
        ]
    )
    print(f"Projekt: {project_id} ({'vorhanden' if project else 'neu'})")

    for key, display in ROLES.items():
        api.call(
            "POST",
            f"/projects/{project_id}/roles",
            {"roleKey": key, "displayName": display},
            ok_conflict=True,
        )
    print(f"Rollen: {', '.join(ROLES)}")

    # Web app: code flow, client secret via Basic, JWT access tokens with roles.
    # devMode allows the http://localhost redirect (finding for ADR: separate dev app later?).
    app_config = {
        "redirectUris": REDIRECT_URIS,
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"],
        "appType": "OIDC_APP_TYPE_WEB",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
        "postLogoutRedirectUris": POST_LOGOUT_URIS,
        "devMode": True,
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
        "accessTokenRoleAssertion": True,
        "idTokenRoleAssertion": True,
    }
    app = find_one(
        api, f"/projects/{project_id}/apps/_search", {"nameQuery": {"name": APP_NAME, "method": eq}}
    )
    if app:
        # Secret cannot be read back: update config, generate a new secret.
        app_id, client_id = app["id"], app["oidcConfig"]["clientId"]
        api.call("PUT", f"/projects/{project_id}/apps/{app_id}/oidc_config", app_config)
        secret = api.call(
            "POST", f"/projects/{project_id}/apps/{app_id}/oidc_config/_generate_client_secret"
        )["clientSecret"]
    else:
        created = api.call(
            "POST", f"/projects/{project_id}/apps/oidc", {"name": APP_NAME, **app_config}
        )
        client_id, secret = created["clientId"], created["clientSecret"]
    print(f"Web-App: client_id {client_id} ({'vorhanden, neues Secret' if app else 'neu'})")

    # Test user without any admin role, only a project grant.
    password = f"Spike-{secrets.token_urlsafe(9)}-7a!"
    user = find_one(
        api, "/users/_search", {"userNameQuery": {"userName": SPIKE_USER, "method": eq}}
    )
    if user:
        user_id = user["id"]
        api.call(
            "POST", f"/users/{user_id}/password", {"password": password, "noChangeRequired": True}
        )
    else:
        user_id = api.call(
            "POST",
            "/users/human/_import",
            {
                "userName": SPIKE_USER,
                "profile": {
                    "firstName": "Spike",
                    "lastName": "Pflegekraft WB1",
                    "displayName": "Spike WB1",
                },
                "email": {"email": "spike-wb1@example.invalid", "isEmailVerified": True},
                "password": password,
                "passwordChangeRequired": False,
            },
        )["userId"]
    api.call(
        "POST",
        f"/users/{user_id}/grants",
        {"projectId": project_id, "roleKeys": ["nurse_wb1"]},
        ok_conflict=True,
    )
    login_name = api.call("GET", f"/users/{user_id}")["user"]["preferredLoginName"]

    upsert_env(
        env_path,
        {
            "OIDC_CLIENT_ID": client_id,
            "OIDC_CLIENT_SECRET": secret,
            "OIDC_AUDIENCE": project_id,
            "ZITADEL_PROJECT_ID": project_id,
        },
    )
    print(
        "OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_AUDIENCE, ZITADEL_PROJECT_ID "
        f"in {env_path} geschrieben."
    )
    print(f"Testnutzer (Wegwerf, nur Rolle nurse_wb1): {login_name} / {password}")


# --- login ---------------------------------------------------------------------------------


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def basic_auth(client_id: str, secret: str) -> dict[str, str]:
    # RFC 6749 2.3.1: form-encode id and secret before base64.
    pair = f"{urllib.parse.quote(client_id, safe='')}:{urllib.parse.quote(secret, safe='')}"
    return {"Authorization": "Basic " + base64.b64encode(pair.encode()).decode()}


def wait_for_request(path: str, timeout: int) -> dict[str, str] | None:
    """Waits for one browser request to http://localhost:3000<path>; returns its query params."""
    captured: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            if url.path != path:
                self.send_response(404)
                self.end_headers()
                return
            captured.update(dict(urllib.parse.parse_qsl(url.query)))
            captured["_hit"] = "1"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Spike: angekommen, Fenster kann zu.")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 3000), Handler)
    deadline = time.monotonic() + timeout
    # Other requests (e.g. /favicon.ico) get a 404 and we keep waiting until the deadline.
    while "_hit" not in captured and (left := deadline - time.monotonic()) > 0:
        server.timeout = left
        server.handle_request()
    server.server_close()
    return captured if "_hit" in captured else None


def result(name: str, ok: bool, detail: str) -> None:
    print(f"[{'OK ' if ok else 'NEIN'}] {name}: {detail}")


def login(env_path: Path) -> None:
    env = read_env(env_path)
    needed = ["OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_AUDIENCE"]
    if missing := [k for k in needed if not env.get(k)]:
        sys.exit(f"Fehlt in der .env-Datei: {', '.join(missing)} (erst 'setup' ausführen).")
    issuer, client_id, secret, audience = (env[k] for k in needed)
    auth = basic_auth(client_id, secret)
    _, _, meta = http("GET", issuer.rstrip("/") + "/.well-known/openid-configuration")

    scopes = (
        "openid profile offline_access "
        f"urn:zitadel:iam:org:project:id:{audience}:aud urn:zitadel:iam:org:projects:roles"
    )
    state, nonce = secrets.token_urlsafe(16), secrets.token_urlsafe(16)
    verifier = secrets.token_urlsafe(64)
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    authorize_url = (
        meta["authorization_endpoint"]
        + "?"
        + urllib.parse.urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": LOCAL_REDIRECT,
                "scope": scopes,
                "state": state,
                "nonce": nonce,
                "prompt": "login",
                "login_hint": SPIKE_USER,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
    )
    print("1) Im Browser anmelden (öffnet sich gleich, sonst Adresse kopieren):\n" + authorize_url)
    webbrowser.open(authorize_url)
    callback = wait_for_request("/auth/callback", timeout=300)
    if not callback or "code" not in callback:
        sys.exit(f"Kein Code erhalten: {callback}")
    result(
        "state",
        callback.get("state") == state,
        "stimmt überein" if callback.get("state") == state else "abweichend",
    )

    status, _, tokens = http(
        "POST",
        meta["token_endpoint"],
        headers=auth,
        form={
            "grant_type": "authorization_code",
            "code": callback["code"],
            "redirect_uri": LOCAL_REDIRECT,
            "code_verifier": verifier,
        },
    )
    result(
        "Code einlösen (Basic + PKCE)", status == 200, f"HTTP {status} {tokens.get('error', '')}"
    )
    if status != 200:
        sys.exit(1)
    access, refresh, id_token = (
        tokens["access_token"],
        tokens.get("refresh_token"),
        tokens.get("id_token"),
    )

    # Access token: JWT (three parts), signed with an allowed algorithm, verifiable via JWKS.
    is_jwt = access.count(".") == 2
    result("Access-Token ist JWT", is_jwt, "drei Teile" if is_jwt else "opak")
    if is_jwt:
        header = jwt.get_unverified_header(access)
        print(
            f"     Header: alg={header.get('alg')} typ={header.get('typ')} "
            f"kid vorhanden={'kid' in header}"
        )
        jwks = jwt.PyJWKClient(meta["jwks_uri"])
        try:
            claims = jwt.decode(
                access,
                jwks.get_signing_key_from_jwt(access).key,
                algorithms=["RS256", "ES256"],
                audience=audience,
                issuer=issuer,
            )
            result("Signatur/iss/aud/exp per JWKS", True, "gültig")
        except jwt.PyJWTError as error:
            claims = jwt.decode(access, options={"verify_signature": False})
            result("Signatur/iss/aud/exp per JWKS", False, str(error))
        aud = claims.get("aud")
        result(
            "aud enthält Projekt-ID",
            audience in (aud if isinstance(aud, list) else [aud]),
            f"aud={aud}",
        )
        roles = claims.get(ROLES_CLAIM)
        result(
            "Rollen-Claim im Access-Token",
            isinstance(roles, dict) and "nurse_wb1" in roles,
            f"{ROLES_CLAIM} = {json.dumps(roles)}",
        )
        print(f"     Claim-Namen: {sorted(claims)}")
        print(
            f"     Laufzeit: {claims.get('exp', 0) - claims.get('iat', 0)} s; "
            f"client_id/azp: {claims.get('client_id') or claims.get('azp')}"
        )
    if id_token:
        id_claims = jwt.decode(id_token, options={"verify_signature": False})
        result("ID-Token nonce", id_claims.get("nonce") == nonce, "stimmt überein")
        print(f"     ID-Token-Claims: {sorted(id_claims)}")
    result("Refresh-Token erhalten (offline_access)", bool(refresh), "ja" if refresh else "nein")

    # App tokens must not be usable against Zitadel's own APIs (password change via auth API).
    status, _, _ = http(
        "PUT",  # Auth API v1: PUT /auth/v1/users/me/password
        issuer.rstrip("/") + "/auth/v1/users/me/password",
        headers={"Authorization": f"Bearer {access}"},
        json_body={"oldPassword": "x", "newPassword": "y"},
    )
    result("App-Token kann Zitadel-Auth-API NICHT nutzen", status in (401, 403), f"HTTP {status}")

    # Revocation: refresh token first, then access token; afterwards refresh must fail.
    if refresh:
        status, _, _ = http(
            "POST",
            meta["revocation_endpoint"],
            headers=auth,
            form={"token": refresh, "token_type_hint": "refresh_token"},
        )
        result("Refresh-Token widerrufen", status == 200, f"HTTP {status}")
        status, _, body = http(
            "POST",
            meta["token_endpoint"],
            headers=auth,
            form={"grant_type": "refresh_token", "refresh_token": refresh},
        )
        result(
            "Refresh nach Widerruf scheitert",
            status >= 400,
            f"HTTP {status} {body.get('error', '')}",
        )
    status, _, _ = http(
        "POST",
        meta["revocation_endpoint"],
        headers=auth,
        form={"token": access, "token_type_hint": "access_token"},
    )
    result("Access-Token widerrufen", status == 200, f"HTTP {status}")
    status, _, body = http(
        "POST", meta["introspection_endpoint"], headers=auth, form={"token": access}
    )
    result(
        "Introspektion nach Widerruf: active=false",
        status == 200 and body.get("active") is False,
        f"HTTP {status} active={body.get('active')}",
    )
    print(
        "     Hinweis: ein JWT bleibt lokal (JWKS) bis exp gültig – "
        "Widerruf wirkt nur bei Introspektion."
    )

    # end_session with client_id, without id_token_hint (no token in the browser URL).
    logout_url = (
        meta["end_session_endpoint"]
        + "?"
        + urllib.parse.urlencode(
            {"client_id": client_id, "post_logout_redirect_uri": LOCAL_POST_LOGOUT}
        )
    )
    status, headers, _ = http("GET", logout_url)
    result(
        "end_session ohne id_token_hint (Server)",
        status in (302, 303),
        f"HTTP {status} -> {headers.get('location', '')[:120]}",
    )
    print("2) Logout im Browser (mit der Zitadel-Sitzung von eben):\n" + logout_url)
    webbrowser.open(logout_url)
    back = wait_for_request("/", timeout=120)
    result(
        "end_session leitet zur post_logout_redirect_uri",
        back is not None,
        "zurück auf localhost:3000/" if back else "nicht angekommen (120 s)",
    )


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("setup", "login"):
        sys.exit("Aufruf: python -m scripts.zitadel_spike setup|login [../../.env]")
    path = Path(sys.argv[2] if len(sys.argv) > 2 else "../../.env")
    {"setup": setup, "login": login}[sys.argv[1]](path)
