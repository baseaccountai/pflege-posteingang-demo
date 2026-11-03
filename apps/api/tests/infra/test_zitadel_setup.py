"""F01-AC16, F01-AC17, F01-AC18, F01-AC22: demo users as code, without admin rights,
passwords reset - and the passwords of the public demo only from secrets, never the file.

The Zitadel Management API is replaced by a recording fake; the tests check which calls
the setup script makes for a given demo-users.json.
"""

import copy
import json
from pathlib import Path

import pytest
from zitadel.setup import (
    ConfigError,
    demo_passwords,
    load_config,
    reset_passwords,
    setup,
)

CONFIG_PATH = Path(__file__).parents[4] / "infra" / "demo-users.json"


class FakeZitadel:
    """Records calls; answers like an empty (or pre-filled) Zitadel organization."""

    def __init__(
        self,
        existing_users: dict[str, str] | None = None,
        app_exists: bool = False,
        memberships: dict[str, list[str]] | None = None,
    ):
        self.calls: list[tuple[str, str, object]] = []
        self.users = dict(existing_users or {})  # username -> id
        self.app_exists = app_exists
        self.memberships = memberships or {}  # user id -> org member roles

    def call(self, method: str, path: str, body: object = None) -> dict:
        self.calls.append((method, path, body))
        if path == "/projects/_search":
            return {"result": [{"id": "p1"}]} if self.app_exists else {}
        if path == "/projects":
            return {"id": "p1"}
        if path == "/projects/p1/apps/_search":
            if self.app_exists:
                return {"result": [{"id": "a1", "oidcConfig": {"clientId": "c1"}}]}
            return {}
        if path == "/projects/p1/apps/oidc":
            return {"clientId": "c1", "clientSecret": "s3cret"}
        if path.endswith("_generate_client_secret"):
            return {"clientSecret": "rotated"}
        if path == "/users/_search":
            name = body["queries"][0]["userNameQuery"]["userName"]
            return {"result": [{"id": self.users[name]}]} if name in self.users else {}
        if path == "/users/human/_import":
            user_id = f"id-{body['userName']}"
            self.users[body["userName"]] = user_id
            return {"userId": user_id}
        if path == "/orgs/me/members/_search":
            user_id = body["queries"][0]["userIdQuery"]["userId"]
            roles = self.memberships.get(user_id, [])
            return {"result": [{"userId": user_id, "roles": roles}]} if roles else {}
        return {}

    def paths(self, method: str | None = None) -> list[str]:
        return [path for m, path, _ in self.calls if method in (None, m)]

    def bodies(self, path: str) -> list[object]:
        return [body for _, p, body in self.calls if p == path]


# Stand-ins for the GitHub secrets; the real ones exist only there and in the .env.
SECRETS = {
    "DEMO_PASSWORD_WB1": "secret-wb1-0123456789",
    "DEMO_PASSWORD_WB2": "secret-wb2-0123456789",
    "DEMO_PASSWORD_PDL": "secret-pdl-0123456789",
}
PASSWORDS = {
    "pflege-wb1": "secret-wb1-0123456789",
    "pflege-wb2": "secret-wb2-0123456789",
    "pdl": "secret-pdl-0123456789",
}


@pytest.fixture
def config() -> dict:
    return load_config(CONFIG_PATH)


def test_demo_file_defines_three_demo_users_with_one_project_role_each(config):
    assert {u["username"]: u["roles"] for u in config["users"]} == {
        "pflege-wb1": ["nurse_wb1"],
        "pflege-wb2": ["nurse_wb2"],
        "pdl": ["pdl"],
    }


def test_fresh_setup_creates_project_roles_app_and_users(config):
    api = FakeZitadel()
    result = setup(api, config, PASSWORDS)

    assert api.bodies("/projects") == [{"name": "pflege-posteingang", "projectRoleAssertion": True}]
    assert [b["roleKey"] for b in api.bodies("/projects/p1/roles")] == [
        "nurse_wb1",
        "nurse_wb2",
        "pdl",
    ]
    [app] = api.bodies("/projects/p1/apps/oidc")
    assert app["authMethodType"] == "OIDC_AUTH_METHOD_TYPE_BASIC"
    assert app["accessTokenType"] == "OIDC_TOKEN_TYPE_JWT"
    assert app["accessTokenRoleAssertion"] is True
    assert app["redirectUris"] == config["app"]["redirect_uris"]
    assert app["postLogoutRedirectUris"] == config["app"]["post_logout_redirect_uris"]
    imported = api.bodies("/users/human/_import")
    assert [b["userName"] for b in imported] == ["pflege-wb1", "pflege-wb2", "pdl"]
    assert all(b["passwordChangeRequired"] is False for b in imported)
    assert api.bodies("/users/id-pdl/grants") == [{"projectId": "p1", "roleKeys": ["pdl"]}]
    assert result == {"client_id": "c1", "client_secret": "s3cret", "project_id": "p1"}


def test_rerun_keeps_client_secret_and_resets_passwords(config):
    users = {"pflege-wb1": "u1", "pflege-wb2": "u2", "pdl": "u3"}
    api = FakeZitadel(existing_users=users, app_exists=True)
    result = setup(api, config, PASSWORDS)

    assert "/projects" not in api.paths("POST")
    assert "/projects/p1/apps/oidc" not in api.paths()
    assert not [p for p in api.paths() if p.endswith("_generate_client_secret")]
    assert "/users/human/_import" not in api.paths()
    assert api.bodies("/users/u1/password") == [
        {"password": "secret-wb1-0123456789", "noChangeRequired": True}
    ]
    assert result == {"client_id": "c1", "client_secret": None, "project_id": "p1"}


def test_rotate_secret_generates_a_new_one(config):
    api = FakeZitadel(app_exists=True)
    assert setup(api, config, PASSWORDS, rotate_secret=True)["client_secret"] == "rotated"


def test_spike_user_is_removed(config):
    api = FakeZitadel(existing_users={"spike-wb1": "spike"})
    setup(api, config, PASSWORDS)
    assert ("DELETE", "/users/spike", None) in api.calls


def test_setup_never_touches_admin_memberships(config):
    # F01-AC17: no organization/instance member roles for demo users, ever.
    api = FakeZitadel()
    setup(api, config, PASSWORDS)
    writes = [p for m, p, _ in api.calls if m in ("POST", "PUT", "DELETE") and "_search" not in p]
    assert not [p for p in writes if "/members" in p or p.startswith("/admin")]


def test_setup_fails_if_a_demo_user_has_an_admin_membership(config):
    api = FakeZitadel(memberships={"id-pdl": ["ORG_OWNER"]})
    with pytest.raises(ConfigError, match="pdl"):
        setup(api, config, PASSWORDS)


ADMIN_PDL = {"pflege-wb1": "u1", "pflege-wb2": "u2", "pdl": "u3"}


def password_writes(api: FakeZitadel) -> list[str]:
    return [p for p in api.paths("POST") if p.endswith("/password")]


def test_setup_checks_existing_accounts_before_publishing_any_password(config):
    # An existing admin account must never receive the public demo password.
    api = FakeZitadel(existing_users=ADMIN_PDL, memberships={"u3": ["ORG_OWNER"]})
    with pytest.raises(ConfigError, match="pdl"):
        setup(api, config, PASSWORDS)
    assert password_writes(api) == []


def test_password_reset_refuses_admin_accounts_without_writing(config):
    api = FakeZitadel(existing_users=ADMIN_PDL, memberships={"u3": ["ORG_OWNER"]})
    with pytest.raises(ConfigError, match="pdl"):
        reset_passwords(api, config, PASSWORDS)
    assert password_writes(api) == []


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(lambda c: c["users"][0].update(roles=["ORG_OWNER"]), id="admin-role"),
        pytest.param(lambda c: c["users"][0].update(roles=["unknown"]), id="undefined-role"),
        pytest.param(lambda c: c["users"][1].update(username="pflege-wb1"), id="duplicate"),
        pytest.param(lambda c: c["users"][0].update(email="x@real-domain.de"), id="real-mail"),
    ],
)
def test_invalid_demo_files_are_rejected(tmp_path, change):
    data = json.loads(CONFIG_PATH.read_text())
    broken = copy.deepcopy(data)
    change(broken)
    path = tmp_path / "demo-users.json"
    path.write_text(json.dumps(broken))
    with pytest.raises(ConfigError):
        load_config(path)


def test_password_reset_only_sets_passwords(config):
    # F01-AC18: the 15-minute workflow; it must not create, grant or delete anything.
    users = {"pflege-wb1": "u1", "pflege-wb2": "u2", "pdl": "u3"}
    api = FakeZitadel(existing_users=users)
    reset_passwords(api, config, PASSWORDS)
    writes = [(m, p) for m, p, _ in api.calls if "_search" not in p]
    assert writes == [
        ("POST", "/users/u1/password"),
        ("POST", "/users/u2/password"),
        ("POST", "/users/u3/password"),
    ]


def test_password_reset_fails_if_a_demo_user_is_missing(config):
    api = FakeZitadel(existing_users={"pflege-wb1": "u1"})
    with pytest.raises(ConfigError, match="pflege-wb2"):
        reset_passwords(api, config, PASSWORDS)


# --- F01-AC22: passwords of the public demo only from secrets ------------------------------


def test_the_file_holds_only_local_passwords_and_the_names_of_the_secrets(config):
    for user in config["users"]:
        assert "password" not in user
        assert user["local_password"]  # Keycloak and tests on the own machine
        assert user["password_env"].startswith("DEMO_PASSWORD_")


def test_passwords_are_read_from_the_environment(config):
    assert demo_passwords(config, SECRETS) == PASSWORDS


def test_setup_and_reset_set_the_passwords_from_the_secrets(config):
    api = FakeZitadel()
    setup(api, config, PASSWORDS)
    assert [b["password"] for b in api.bodies("/users/human/_import")] == list(PASSWORDS.values())
    api = FakeZitadel(existing_users={"pflege-wb1": "u1", "pflege-wb2": "u2", "pdl": "u3"})
    reset_passwords(api, config, PASSWORDS)
    assert api.bodies("/users/u3/password") == [
        {"password": "secret-pdl-0123456789", "noChangeRequired": True}
    ]


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(None, id="missing"),
        pytest.param("", id="empty"),
        pytest.param("short-0123456", id="shorter-than-16"),
        pytest.param("Pflege-WB2-Demo!", id="the-old-public-one"),
    ],
)
def test_a_missing_short_or_old_password_stops_everything(config, value):
    env = dict(SECRETS)
    if value is None:
        del env["DEMO_PASSWORD_WB2"]
    else:
        env["DEMO_PASSWORD_WB2"] = value
    with pytest.raises(ConfigError, match="DEMO_PASSWORD_WB2"):
        demo_passwords(config, env)


def test_a_user_without_the_name_of_its_secret_is_rejected(tmp_path):
    data = json.loads(CONFIG_PATH.read_text())
    del data["users"][0]["password_env"]
    path = tmp_path / "demo-users.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ConfigError, match="pflege-wb1"):
        load_config(path)
