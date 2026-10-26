"""F01-AC8: business routes need a short-lived BFF assertion (X-Bff-Assertion).

The assertion is an HS256 JWS signed with BFF_API_SECRET, shared only by the Next.js BFF and
the API: {sid_hash, aud: "pflege-api", iat, exp: iat + 60 s}. A valid user token alone,
e.g. one copied out of the BFF, is not enough to call the API directly.
"""

import hashlib
import time

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.bff import InvalidBffAssertion, bff_session, verify_bff_assertion

SECRET = "test-bff-secret-" + "x" * 48  # 64 bytes, also long enough for HS512
SID_HASH = hashlib.sha256(b"session-id").hexdigest()


def assertion(secret: str = SECRET, algorithm: str = "HS256", **overrides) -> str:
    now = int(time.time())
    payload = {"sid_hash": SID_HASH, "aud": "pflege-api", "iat": now, "exp": now + 60}
    payload.update(overrides)
    payload = {key: value for key, value in payload.items() if value is not None}
    return jwt.encode(payload, secret, algorithm=algorithm)


def test_valid_assertion_returns_sid_hash():
    assert verify_bff_assertion(assertion(), SECRET) == SID_HASH


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(None, id="missing"),
        pytest.param("", id="empty"),
        pytest.param("not-a-jws", id="garbage"),
        pytest.param(
            assertion(iat=int(time.time()) - 300, exp=int(time.time()) - 120), id="expired"
        ),
        pytest.param(assertion(secret="another-secret-" + "y" * 49), id="wrong-signature"),
        pytest.param(assertion(aud="other-api"), id="wrong-aud"),
        pytest.param(assertion(exp=int(time.time()) + 3600), id="lifetime-too-long"),
        pytest.param(assertion(sid_hash="not-a-sha256"), id="malformed-sid-hash"),
        pytest.param(assertion(sid_hash=None), id="no-sid-hash"),
        pytest.param(assertion(algorithm="HS512"), id="other-algorithm"),
    ],
)
def test_invalid_assertions_are_rejected(token):
    with pytest.raises(InvalidBffAssertion):
        verify_bff_assertion(token, SECRET)


def test_short_secret_is_refused_as_configuration_error():
    with pytest.raises(ValueError):
        verify_bff_assertion(assertion(), "short")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("BFF_API_SECRET", SECRET)
    app = FastAPI()

    @app.get("/probe")
    def probe(sid_hash: str = Depends(bff_session)) -> dict:
        return {"sid_hash": sid_hash}

    return TestClient(app)


def test_route_without_assertion_answers_401_without_details(client):
    response = client.get("/probe")
    assert response.status_code == 401
    assert response.json() == {"detail": "Nicht angemeldet"}


def test_route_with_bad_assertion_answers_401(client):
    response = client.get("/probe", headers={"X-Bff-Assertion": assertion(aud="other-api")})
    assert response.status_code == 401


def test_route_with_valid_assertion_gets_sid_hash(client):
    response = client.get("/probe", headers={"X-Bff-Assertion": assertion()})
    assert response.status_code == 200
    assert response.json() == {"sid_hash": SID_HASH}
