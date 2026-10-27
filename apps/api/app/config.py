"""Runtime configuration, read from environment variables.

Providers are switched by configuration only (never by code changes):
  LLM_PROVIDER=mistral|ollama, OCR_PROVIDER=mistral|docling (fake: tests only, both)
"""

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # "fake": rule-based stand-in for tests and the e2e run without a Mistral key.
    llm_provider: Literal["mistral", "ollama", "fake"] = "mistral"
    # "fake": canned OCR text for tests and the e2e run without a Mistral key.
    ocr_provider: Literal["mistral", "docling", "fake"] = "mistral"
    docling_base_url: str = "http://localhost:5001"
    # Only with OCR_PROVIDER=fake: folder samples/ whose files the fake "reads" (e2e).
    fake_ocr_samples: str = ""
    # Secret; empty means OCR/LLM calls fail with "unavailable" (never a silent fallback).
    mistral_api_key: str = ""
    mistral_ocr_model: str = "mistral-ocr-latest"
    mistral_chat_model: str = "mistral-small-latest"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3:8b"
    # Shared with the Next.js BFF only; empty means "not configured" and every request fails.
    bff_api_secret: str = ""
    # Login role api_gateway via the transaction pooler; empty: business routes answer 503.
    database_url: str = ""
    # Identity provider (F01-AC19: switching IdP is configuration only).
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_roles_claim: str = "urn:zitadel:iam:org:project:roles"


def get_settings() -> Settings:
    """FastAPI dependency; tests can replace it via app.dependency_overrides."""
    return Settings()
