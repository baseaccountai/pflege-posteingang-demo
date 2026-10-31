def test_health_reports_providers(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ok",
        "llm_provider": "mistral",
        "ocr_provider": "mistral",
        "agent_token": "off",  # F08-AC2: no agent configured
    }


def test_health_names_the_way_of_the_agent_token():
    # F08-AC2: /projekt says openly which way is active - here the fallback.
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app
    from tests.support.oidc import AGENT_SIGNING_KEY, AUDIENCE, ISSUER, test_verifier

    settings = Settings(
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        agent_token_mode="self_signed",
        agent_id="agent-test",
        agent_signing_key=AGENT_SIGNING_KEY,
    )
    with TestClient(create_app(settings, verifier=test_verifier())) as api:
        assert api.get("/health").json()["agent_token"] == "self_signed"


def test_health_reflects_env(monkeypatch, make_client):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OCR_PROVIDER", "docling")
    body = make_client().get("/health").json()
    assert body["llm_provider"] == "ollama"
    assert body["ocr_provider"] == "docling"


def test_unknown_provider_is_rejected(monkeypatch, make_client):
    import pytest
    from pydantic import ValidationError

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        make_client()
