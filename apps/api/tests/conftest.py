from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch) -> Callable[[], TestClient]:
    """Build a fresh app per call, so settings are re-read from the environment."""
    # Start every test from the documented defaults, independent of the developer's shell.
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OCR_PROVIDER", raising=False)
    return lambda: TestClient(create_app())


@pytest.fixture
def client(make_client: Callable[[], TestClient]) -> TestClient:
    return make_client()
