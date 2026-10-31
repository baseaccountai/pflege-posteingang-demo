"""Spike F08 task 1 (F08-AC1, AC2a): does Zitadel exchange a nurse's token for an agent token?

Throwaway draft like scripts/zitadel_spike.py; the result goes into ADR 0012. Run by the
applicant in their own terminal, never in CI. Prints claims and results, never a token
or secret.

Before: in the Zitadel console (instance admin) switch on
  1. Settings > Features: "Token Exchange" (beta),
  2. Default settings > Security: "Allow impersonation".

    cd apps/api && uv run python -m scripts.agent_token_spike setup ../../.env
    cd apps/api && uv run python -m scripts.agent_token_spike exchange ../../.env

setup     With ZITADEL_ADMIN_PAT (organization owner): creates or reuses the service user
          `pp-agent` (JWT access tokens, client secret) with the organization role
          ORG_END_USER_IMPERSONATOR, and the confidential app `pflege-posteingang-agent`
          that may use the token exchange grant. Writes AGENT_CLIENT_ID/_SECRET (service
          user) and AGENT_EXCHANGE_CLIENT_ID/_SECRET (app) into the .env file.
exchange  Logs a demo nurse in through the browser (default pflege-wb1), fetches the agent's
          own token (client credentials), exchanges the nurse's token for an agent token
          and shows its claims: iss, aud, sub, act, exp - iat, roles.
"""

import hashlib
import json
import secrets
import sys
import urllib.parse
import webbrowser
from pathlib import Path

import jwt

from scripts.provision_db_roles import read_env, upsert_env
from scripts.zitadel_spike import (
    LOCAL_REDIRECT,
    ROLES_CLAIM,
    Management,
    b64url,
    basic_auth,
    find_one,
    http,
    result,
    wait_for_request,
)

AGENT_USER = "pp-agent"
AGENT_APP = "pflege-posteingang-agent"
PROJECT_NAME = "pflege-posteingang"
EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"
JWT_TYPE = "urn:ietf:params:oauth:token-type:jwt"
EQ = "TEXT_QUERY_METHOD_EQUALS"


def setup(env_path: Path) -> None:
    env = read_env(env_path)
    issuer, pat = env.get("OIDC_ISSUER"), env.get("ZITADEL_ADMIN_PAT")
    if not issuer or not pat:
        sys.exit("OIDC_ISSUER und ZITADEL_ADMIN_PAT müssen in der .env-Datei stehen.")
    api = Management(issuer, pat)

    _, _, meta = http("GET", issuer.rstrip("/") + "/.well-known/openid-configuration")
    offered = EXCHANGE in meta.get("grant_types_supported", [])
    result("Token Exchange im Discovery", offered, "ja" if offered else "Feature noch aus?")

    # The agent: a service user whose access tokens are JWTs (the API verifies them via JWKS).
    user = find_one(
        api, "/users/_search", {"userNameQuery": {"userName": AGENT_USER, "method": EQ}}
    )
    if user:
        user_id = user["id"]
    else:
        user_id = api.call(
            "POST",
            "/users/machine",
            {
                "userName": AGENT_USER,
                "name": "Agent Pflege-Posteingang",
                "description": "Handelt im Auftrag einer Pflegekraft (F08)",
                "accessTokenType": "ACCESS_TOKEN_TYPE_JWT",
            },
        )["userId"]
    secret = api.call("PUT", f"/users/{user_id}/secret")
    print(f"Service-User {AGENT_USER}: {user_id} ({'vorhanden' if user else 'neu'}), neues Secret")

    # May act for end users only (no admin memberships), and only in this organization.
    api.call(
        "POST",
        "/orgs/me/members",
        {"userId": user_id, "roles": ["ORG_END_USER_IMPERSONATOR"]},
        ok_conflict=True,
    )
    print("Rolle ORG_END_USER_IMPERSONATOR gesetzt")

    # The client the API authenticates with when it asks for the exchange.
    project = find_one(
        api, "/projects/_search", {"nameQuery": {"name": PROJECT_NAME, "method": EQ}}
    )
    if not project:
        sys.exit(f"Projekt {PROJECT_NAME} fehlt (infra/zitadel/setup.py).")
    project_id = project["id"]
    app_config = {
        "redirectUris": [LOCAL_REDIRECT],
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_TOKEN_EXCHANGE"],
        "appType": "OIDC_APP_TYPE_WEB",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
        "devMode": True,
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
        "accessTokenRoleAssertion": True,
    }
    app = find_one(
        api,
        f"/projects/{project_id}/apps/_search",
        {"nameQuery": {"name": AGENT_APP, "method": EQ}},
    )
    if app:
        app_id, client_id = app["id"], app["oidcConfig"]["clientId"]
        api.call("PUT", f"/projects/{project_id}/apps/{app_id}/oidc_config", app_config)
        app_secret = api.call(
            "POST", f"/projects/{project_id}/apps/{app_id}/oidc_config/_generate_client_secret"
        )["clientSecret"]
    else:
        created = api.call(
            "POST", f"/projects/{project_id}/apps/oidc", {"name": AGENT_APP, **app_config}
        )
        client_id, app_secret = created["clientId"], created["clientSecret"]
    print(f"App {AGENT_APP}: client_id {client_id} ({'vorhanden' if app else 'neu'}), neues Secret")

    upsert_env(
        env_path,
        {
            "AGENT_CLIENT_ID": secret["clientId"],
            "AGENT_CLIENT_SECRET": secret["clientSecret"],
            "AGENT_EXCHANGE_CLIENT_ID": client_id,
            "AGENT_EXCHANGE_CLIENT_SECRET": app_secret,
        },
    )
    print(f"AGENT_CLIENT_ID/_SECRET, AGENT_EXCHANGE_CLIENT_ID/_SECRET in {env_path} geschrieben.")


def nurse_token(meta: dict, client_id: str, secret: str, audience: str, username: str) -> str:
    """Authorization Code + PKCE through the browser, like the web app's login."""
    scopes = (
        "openid profile "
        f"urn:zitadel:iam:org:project:id:{audience}:aud urn:zitadel:iam:org:projects:roles"
    )
    state, verifier = secrets.token_urlsafe(16), secrets.token_urlsafe(64)
    url = (
        meta["authorization_endpoint"]
        + "?"
        + urllib.parse.urlencode(
            {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": LOCAL_REDIRECT,
                "scope": scopes,
                "state": state,
                "prompt": "login",
                "login_hint": username,
                "code_challenge": b64url(hashlib.sha256(verifier.encode()).digest()),
                "code_challenge_method": "S256",
            }
        )
    )
    print(f"1) Im Browser als {username} anmelden (öffnet sich gleich, sonst Adresse kopieren):")
    print(url)
    webbrowser.open(url)
    callback = wait_for_request("/auth/callback", timeout=300)
    if not callback or callback.get("state") != state or "code" not in callback:
        sys.exit(f"Kein gültiger Code erhalten: {sorted(callback or {})}")
    status, _, tokens = http(
        "POST",
        meta["token_endpoint"],
        headers=basic_auth(client_id, secret),
        form={
            "grant_type": "authorization_code",
            "code": callback["code"],
            "redirect_uri": LOCAL_REDIRECT,
            "code_verifier": verifier,
        },
    )
    result("Nutzer-Token", status == 200, f"HTTP {status} {tokens.get('error', '')}")
    if status != 200:
        sys.exit(1)
    return tokens["access_token"]


def show(name: str, token: str) -> dict:
    claims = jwt.decode(token, options={"verify_signature": False})
    print(f"     {name}: iss={claims.get('iss')} aud={claims.get('aud')} sub={claims.get('sub')}")
    lifetime = claims.get("exp", 0) - claims.get("iat", 0)
    print(f"       act={json.dumps(claims.get('act'))} exp-iat={lifetime} s")
    print(f"       {ROLES_CLAIM}={json.dumps(claims.get(ROLES_CLAIM))}")
    print(f"       Claim-Namen: {sorted(claims)}")
    return claims


def exchange(env_path: Path, username: str = "pflege-wb1") -> None:
    env = read_env(env_path)
    needed = [
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_AUDIENCE",
        "AGENT_CLIENT_ID",
        "AGENT_CLIENT_SECRET",
        "AGENT_EXCHANGE_CLIENT_ID",
        "AGENT_EXCHANGE_CLIENT_SECRET",
    ]
    if missing := [k for k in needed if not env.get(k)]:
        sys.exit(f"Fehlt in der .env-Datei: {', '.join(missing)} (erst 'setup' ausführen).")
    issuer, audience = env["OIDC_ISSUER"], env["OIDC_AUDIENCE"]
    _, _, meta = http("GET", issuer.rstrip("/") + "/.well-known/openid-configuration")

    subject = nurse_token(
        meta, env["OIDC_CLIENT_ID"], env["OIDC_CLIENT_SECRET"], audience, username
    )
    nurse = show("Nutzer-Token", subject)

    # 2) The agent's own token: client credentials of the service user.
    status, _, tokens = http(
        "POST",
        meta["token_endpoint"],
        headers=basic_auth(env["AGENT_CLIENT_ID"], env["AGENT_CLIENT_SECRET"]),
        form={
            "grant_type": "client_credentials",
            "scope": f"openid urn:zitadel:iam:org:project:id:{audience}:aud",
        },
    )
    result(
        "Agenten-Token (Client Credentials)",
        status == 200,
        f"HTTP {status} {tokens.get('error', '')}",
    )
    if status != 200:
        sys.exit(1)
    actor = tokens["access_token"]
    agent = show("Agenten-Token", actor)

    # 3) The exchange: subject = nurse, actor = agent; the result should carry act.sub = agent.
    form = {
        "grant_type": EXCHANGE,
        "subject_token": subject,
        "subject_token_type": ACCESS_TOKEN,
        "actor_token": actor,
        "actor_token_type": ACCESS_TOKEN,
        "requested_token_type": JWT_TYPE,
    }
    auth = basic_auth(env["AGENT_EXCHANGE_CLIENT_ID"], env["AGENT_EXCHANGE_CLIENT_SECRET"])
    status, _, tokens = http("POST", meta["token_endpoint"], headers=auth, form=form)
    detail = f"HTTP {status} {tokens.get('error', '')} {tokens.get('error_description', '')}"
    result("Token Exchange", status == 200, detail)
    if status != 200:
        sys.exit(1)
    print(f"     issued_token_type={tokens.get('issued_token_type')}")
    claims = show("Getauschtes Token", tokens["access_token"])

    # What the API will check (F08-AC3), with the real claims.
    aud = claims.get("aud")
    aud = aud if isinstance(aud, list) else [aud]
    lifetime = claims.get("exp", 0) - claims.get("iat", 0)
    result("sub = Pflegekraft", claims.get("sub") == nurse.get("sub"), str(claims.get("sub")))
    act = claims.get("act") or {}
    result("act.sub = Agent", act.get("sub") == agent.get("sub"), json.dumps(act))
    result("aud enthält Projekt", audience in aud, str(aud))
    result("Rollen der Pflegekraft", claims.get(ROLES_CLAIM) == nurse.get(ROLES_CLAIM), "")
    result("Laufzeit ≤ 300 s", lifetime <= 300, f"{lifetime} s")
    jwks = jwt.PyJWKClient(meta["jwks_uri"])
    try:
        jwt.decode(
            tokens["access_token"],
            jwks.get_signing_key_from_jwt(tokens["access_token"]).key,
            algorithms=["RS256", "ES256"],
            audience=audience,
            issuer=issuer,
        )
        result("Signatur per JWKS", True, "gültig")
    except jwt.PyJWTError as error:
        result("Signatur per JWKS", False, str(error))


if __name__ == "__main__":
    commands = {"setup": setup, "exchange": exchange}
    if len(sys.argv) < 3 or sys.argv[1] not in commands:
        sys.exit(
            "Aufruf: python -m scripts.agent_token_spike setup|exchange <pfad/zur/.env> [nutzer]"
        )
    commands[sys.argv[1]](Path(sys.argv[2]), *sys.argv[3:])
