"""Local embeddings through Ollama (F05-AC13), e.g. `bge-m3`: multilingual, 1024 dimensions.

A model with another vector size is refused instead of storing vectors that do not fit
the column (and could never be compared with the others).
"""

import httpx

from app.providers.embeddings.base import DIMENSION, EmbeddingUnavailable, checked

TIMEOUT_SECONDS = 120  # a local model on a laptop is slow


class OllamaEmbeddings:
    dimension = DIMENSION

    def __init__(self, base_url: str, model: str, timeout: float = TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/embed", json={"model": self.model_name, "input": texts}
                )
            response.raise_for_status()
            vectors = response.json()["embeddings"]
        except httpx.HTTPStatusError as error:
            raise EmbeddingUnavailable(f"Ollama answered {error.response.status_code}") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            failure = type(error).__name__
            raise EmbeddingUnavailable(f"Ollama embeddings failed: {failure}") from None
        return checked(vectors, len(texts))
