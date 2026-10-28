"""Mistral embeddings (`mistral-embed`, 1024 dimensions) for the public demo.

Texts are sent in batches; the answer is put back in input order by its "index". Every
transport or HTTP failure becomes EmbeddingUnavailable; the API key never appears in messages.
"""

import httpx

from app.providers.embeddings.base import DIMENSION, EmbeddingUnavailable, checked

EMBEDDINGS_URL = "https://api.mistral.ai/v1/embeddings"
MODEL = "mistral-embed"
BATCH_SIZE = 32  # chunks of up to 800 tokens: well below Mistral's request limit
TIMEOUT_SECONDS = 30


class MistralEmbeddings:
    dimension = DIMENSION

    def __init__(self, api_key: str, model: str = MODEL, timeout: float = TIMEOUT_SECONDS):
        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise EmbeddingUnavailable("MISTRAL_API_KEY is not set")
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for start in range(0, len(texts), BATCH_SIZE):
                vectors += await self._batch(client, texts[start : start + BATCH_SIZE])
        return vectors

    async def _batch(self, client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
        try:
            response = await client.post(
                EMBEDDINGS_URL,
                json={"model": self.model_name, "input": texts},
                headers={"authorization": f"Bearer {self.api_key}"},
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in data]
        except httpx.HTTPStatusError as error:
            raise EmbeddingUnavailable(f"Mistral answered {error.response.status_code}") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            failure = type(error).__name__
            raise EmbeddingUnavailable(f"Mistral embeddings failed: {failure}") from None
        return checked(vectors, len(texts))
