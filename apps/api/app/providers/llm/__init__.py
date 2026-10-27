"""LLM providers (F03, F05); `create_llm_provider` picks one from LLM_PROVIDER (F03-AC13)."""

from app.config import Settings
from app.providers.llm.base import LlmInvalidOutput, LlmProvider, LlmUnavailable
from app.providers.llm.fake import FakeLlm
from app.providers.llm.mistral import MistralLlm
from app.providers.llm.ollama import OllamaLlm

__all__ = ["LlmInvalidOutput", "LlmProvider", "LlmUnavailable", "create_llm_provider"]


def create_llm_provider(settings: Settings) -> LlmProvider:
    if settings.llm_provider == "mistral":
        return MistralLlm(settings.mistral_api_key, settings.mistral_chat_model)
    if settings.llm_provider == "ollama":
        return OllamaLlm(settings.ollama_base_url, settings.ollama_chat_model)
    return FakeLlm()
