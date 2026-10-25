"""Runtime configuration, read from environment variables.

Providers are switched by configuration only (never by code changes):
  LLM_PROVIDER=mistral|ollama, OCR_PROVIDER=mistral|docling
"""

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: Literal["mistral", "ollama"] = "mistral"
    ocr_provider: Literal["mistral", "docling"] = "mistral"
