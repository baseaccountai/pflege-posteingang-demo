"""Embedding providers (F05); chosen together with the chat model by LLM_PROVIDER (F05-AC13):
mistral -> mistral-embed, ollama -> a local model, fake -> deterministic stand-in."""

from app.config import Settings
from app.providers.embeddings.base import DIMENSION, EmbeddingProvider, EmbeddingUnavailable
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.embeddings.mistral import MistralEmbeddings
from app.providers.embeddings.ollama import OllamaEmbeddings

__all__ = ["DIMENSION", "EmbeddingProvider", "EmbeddingUnavailable", "create_embedding_provider"]


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.llm_provider == "mistral":
        return MistralEmbeddings(settings.mistral_api_key, settings.mistral_embed_model)
    if settings.llm_provider == "ollama":
        return OllamaEmbeddings(settings.ollama_base_url, settings.ollama_embed_model)
    return FakeEmbeddings()
