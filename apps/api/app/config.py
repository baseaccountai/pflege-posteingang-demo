"""Runtime configuration, read from environment variables.

Providers are switched by configuration only (never by code changes):
  LLM_PROVIDER=mistral|ollama, OCR_PROVIDER=mistral|docling
"""

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: Literal["mistral", "ollama"] = "mistral"
    ocr_provider: Literal["mistral", "docling"] = "mistral"
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
