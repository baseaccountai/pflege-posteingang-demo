"""Runtime configuration, read from environment variables.

Providers are switched by configuration only (never by code changes):
  LLM_PROVIDER=mistral|ollama (chat and embeddings), OCR_PROVIDER=mistral|docling
  (fake: tests only, both)
"""

from typing import Literal

from pydantic import Field, model_validator
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
    mistral_embed_model: str = "mistral-embed"
    # Injection checker (F07-AC4): a small, cheap model; with Ollama the chat model is used.
    guard_model: str = "ministral-8b-latest"
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen3:8b"
    # Must give 1024-dimensional vectors like mistral-embed (column chunks.embedding).
    ollama_embed_model: str = "bge-m3"
    # Per model call. A CPU-only laptop writes ~1.2 tokens/s with qwen3:8b (01.11.2026):
    # `make up-local` raises it; nothing else changes.
    ollama_timeout_seconds: float = Field(120, ge=10, le=1800)
    # Questions (F05): chunks below this cosine similarity are no hit. Calibrated with
    # mistral-embed on the seed (F05 Task 8, 28.10.2026): real hits 0.77-0.86, an off-topic
    # question 0.75 - so 0.72 keeps every real hit; the citation check catches the rest.
    rag_min_similarity: float = 0.72
    # Shared with the Next.js BFF only; empty means "not configured" and every request fails.
    bff_api_secret: str = ""
    # Login role api_gateway via the transaction pooler; empty: business routes answer 503.
    database_url: str = ""
    # Identity provider (F01-AC19: switching IdP is configuration only).
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_roles_claim: str = "urn:zitadel:iam:org:project:roles"
    # The agent's own token (F08, ADR 0012). "exchange": Zitadel exchanges the nurse's token
    # (RFC 8693); "self_signed": the API signs it (fallback where the IdP has no exchange).
    # Without AGENT_ID and the mode's secrets there is no agent (its routes answer 503).
    # F02-AC8/AC9: one processing step (OCR, check, suggestion) and when a document counts
    # as stalled. 300 s publicly; the local CPU model needs ~13 min for a suggestion.
    pipeline_step_seconds: int = Field(300, ge=60, le=3600)
    # F08-AC12: the whole agent task. 60 s publicly; the local CPU model needs minutes.
    agent_max_seconds: int = Field(60, ge=1, le=600)
    agent_token_mode: Literal["exchange", "self_signed"] = "exchange"
    agent_id: str = ""  # act.sub: the sub of Zitadel's service user pp-agent
    agent_client_id: str = ""  # secret pair of the service user (client credentials)
    agent_client_secret: str = ""
    agent_exchange_client_id: str = ""  # secret pair of the app allowed to exchange
    agent_exchange_client_secret: str = ""
    agent_signing_key: str = ""  # self_signed only: EC P-256 private key (PEM), secret
    # Accepted at most this long after iat; F08-AC1 says at most 5 minutes. Only the local
    # mode may give it as long as its task, up to 10 minutes (Codex review phase 8).
    agent_token_max_seconds: int = Field(300, ge=1, le=600)

    @model_validator(mode="after")
    def _longer_limits_only_locally(self) -> "Settings":
        """The local CPU model needs minutes (`make up-local`). Such values copied into the
        public deployment by mistake would stretch its limits (Codex review phase 8)."""
        public = {
            "agent_max_seconds": 60,
            "pipeline_step_seconds": 300,
            "agent_token_max_seconds": 300,
        }
        if self.llm_provider != "ollama":
            for name, limit in public.items():
                if getattr(self, name) > limit:
                    raise ValueError(
                        f"{name.upper()} > {limit} only in the local mode (LLM_PROVIDER=ollama)"
                    )
        if self.agent_max_seconds > self.agent_token_max_seconds:
            # The agent must not keep working after its delegation has expired.
            raise ValueError("AGENT_MAX_SECONDS must not exceed AGENT_TOKEN_MAX_SECONDS")
        return self


def get_settings() -> Settings:
    """FastAPI dependency; tests can replace it via app.dependency_overrides."""
    return Settings()
