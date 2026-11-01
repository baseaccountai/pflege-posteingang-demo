"""F11-AC18: with LLM_PROVIDER=ollama every model role runs on the own machine.

Field suggestion, answers and agent (llm), the injection checker (guard) and the embeddings
all go to Ollama - also when a MISTRAL_API_KEY happens to be set, so no text leaves the
computer by mistake ("im lokalen Modus sieht kein fremdes Modell die Daten").
"""

from app.config import Settings
from app.privacy.gateway import create_gateway
from app.providers.embeddings.ollama import OllamaEmbeddings
from app.providers.llm.ollama import OllamaLlm


def test_every_model_role_is_ollama_even_with_a_mistral_key():
    settings = Settings(llm_provider="ollama", mistral_api_key="set-by-mistake")
    gateway = create_gateway(settings, db=None)
    assert isinstance(gateway.llm, OllamaLlm)
    assert isinstance(gateway.guard, OllamaLlm)
    assert isinstance(gateway.embeddings, OllamaEmbeddings)
    assert gateway.llm.model_name == gateway.guard.model_name == "qwen3:8b"
    assert gateway.embeddings.model_name == "bge-m3"
