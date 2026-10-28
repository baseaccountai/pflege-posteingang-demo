"""Embedding interface (F05). Providers are exchangeable by configuration (F05-AC13).

All providers return vectors of the same dimension (1024, the column `chunks.embedding`).
Vectors of different models are still not comparable: every chunk stores `embedding_model`,
and the search only compares vectors of the same model.
"""

from typing import Protocol

DIMENSION = 1024


class EmbeddingUnavailable(Exception):
    """Provider not reachable, timed out, answered with an error or a wrong vector size."""


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per text, in the order of `texts`."""
        ...


def checked(vectors: list[list[float]], expected: int) -> list[list[float]]:
    """The answer must have one vector per text, each with DIMENSION numbers."""
    if len(vectors) != expected or any(len(v) != DIMENSION for v in vectors):
        raise EmbeddingUnavailable(
            f"expected {expected} vectors of {DIMENSION}, got {[len(v) for v in vectors]}"
        )
    return vectors
