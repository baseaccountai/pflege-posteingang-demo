"""F11-AC12: the API is not for browsers - no origin may call it directly (CORS closed).
Only the BFF calls it, server to server, with token and BFF assertion (F01-AC6, AC8)."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings(database_url="")))


@pytest.mark.parametrize(
    "origin", ["https://evil.example", "https://pflege-posteingang-demo.vercel.app"]
)
def test_a_preflight_from_any_origin_is_not_allowed(client, origin):
    response = client.options(
        "/residents",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in response.headers
    assert response.status_code >= 400


def test_a_simple_request_from_a_browser_gets_no_cors_permission(client):
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers
