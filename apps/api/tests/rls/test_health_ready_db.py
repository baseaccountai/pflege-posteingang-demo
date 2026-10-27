"""F10-AC9: with a reachable database /health/ready answers 200."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.rls.conftest import GATEWAY_DSN

pytestmark = pytest.mark.db


def test_ready_asks_the_database(seeded):
    with TestClient(create_app(Settings(database_url=GATEWAY_DSN))) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"db": "ok"}
