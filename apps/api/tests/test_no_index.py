"""F11-AC22: the demo stays out of search engines - every API answer says noindex, also
error answers (a 401 without login, an unknown path)."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings(database_url="", bff_api_secret="s" * 32)))


@pytest.mark.parametrize("path", ["/health", "/residents", "/does-not-exist"])
def test_every_answer_forbids_indexing(client, path):
    response = client.get(path)
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
