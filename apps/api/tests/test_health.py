def test_health_reports_providers(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "llm_provider": "mistral", "ocr_provider": "mistral"}


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
