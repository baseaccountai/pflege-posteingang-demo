"""F01-AC9, F01-AC10, F01-AC12: /me and /residents through the whole API stack.

Real path: access token (JWKS) + BFF assertion -> Principal -> transaction as
`authenticated` with claims -> RLS. Only the IdP is replaced by the test IdP.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.rls.conftest import GATEWAY_DSN, WB1_RESIDENT, WB2_RESIDENT
from tests.support.oidc import (
    AUDIENCE,
    BFF_SECRET,
    ISSUER,
    ROLES_CLAIM,
    access_token,
    bff_assertion,
    test_verifier,
)

pytestmark = pytest.mark.db


@pytest.fixture
def api(seeded: None) -> Iterator[TestClient]:
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
    )
    with TestClient(create_app(settings, verifier=test_verifier())) as client:
        yield client


def as_role(*roles: str, sub: str = "user-1") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token(sub, *roles)}",
        "X-Bff-Assertion": bff_assertion(),
    }


def resident_ids(response) -> set[str]:
    assert response.status_code == 200
    return {resident["id"] for resident in response.json()}


def test_me_returns_derived_principal(api):
    response = api.get("/me", headers=as_role("nurse_wb1", sub="u-wb1"))
    assert response.status_code == 200
    assert response.json() == {
        "sub": "u-wb1",
        "app_role": "nurse",
        "ward_ids": ["wb1"],
        "display_name": "Pflegekraft WB1",
    }


def test_nurse_wb1_sees_only_wb1_residents(api):
    assert resident_ids(api.get("/residents", headers=as_role("nurse_wb1"))) == {WB1_RESIDENT}


def test_nurse_wb2_sees_only_wb2_residents(api):
    assert resident_ids(api.get("/residents", headers=as_role("nurse_wb2"))) == {WB2_RESIDENT}


def test_pdl_sees_both_wards(api):
    response = api.get("/residents", headers=as_role("pdl"))
    assert resident_ids(response) == {WB1_RESIDENT, WB2_RESIDENT}


def test_resident_list_entries_have_display_fields(api):
    [resident] = api.get("/residents", headers=as_role("nurse_wb1")).json()
    assert resident["ward_id"] == "wb1"
    assert resident["display_name"] == "Hr. Muster-Bauer"


def test_nurse_wb1_opens_own_resident(api):
    response = api.get(f"/residents/{WB1_RESIDENT}", headers=as_role("nurse_wb1"))
    assert response.status_code == 200
    assert response.json()["id"] == WB1_RESIDENT


def test_foreign_and_unknown_residents_look_identical(api):
    # F01-AC12: a WB2 nurse must not learn whether a WB1 resident exists.
    headers = as_role("nurse_wb2")
    foreign = api.get(f"/residents/{WB1_RESIDENT}", headers=headers)
    unknown = api.get(f"/residents/{uuid.uuid4()}", headers=headers)
    malformed = api.get("/residents/not-a-uuid", headers=headers)
    for response in (foreign, unknown, malformed):
        assert response.status_code == 404
        assert response.json() == {"detail": "Nicht gefunden"}


def test_valid_token_without_bff_assertion_is_401(api):
    headers = {"Authorization": f"Bearer {access_token('u', 'pdl')}"}
    for path in ("/me", "/residents", f"/residents/{WB1_RESIDENT}"):
        response = api.get(path, headers=headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Nicht angemeldet"}


def test_bff_assertion_without_token_is_401(api):
    response = api.get("/residents", headers={"X-Bff-Assertion": bff_assertion()})
    assert response.status_code == 401
    assert response.json() == {"detail": "Nicht angemeldet"}


def test_forged_token_is_401(api):
    headers = as_role("pdl")
    headers["Authorization"] = headers["Authorization"][:-4] + "AAAA"
    assert api.get("/residents", headers=headers).status_code == 401


def test_token_without_known_role_is_403(api):
    response = api.get("/residents", headers=as_role("admin"))
    assert response.status_code == 403
    assert response.json() == {"detail": "Kein Zugriff"}
