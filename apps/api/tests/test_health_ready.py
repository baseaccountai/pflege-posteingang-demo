"""F10-AC9: /health/ready touches the database (keep-alive) and says when it cannot."""

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


class BrokenDatabase:
    @asynccontextmanager
    async def connection(self):
        raise OSError("connection refused")
        yield


def test_ready_is_503_when_the_database_is_unreachable():
    app = create_app(Settings())
    client = TestClient(app)  # no lifespan: the test sets the database itself
    app.state.database = BrokenDatabase()
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"db": "unavailable"}


def test_ready_is_503_without_a_configured_database():
    response = TestClient(create_app(Settings())).get("/health/ready")
    assert response.status_code == 503
