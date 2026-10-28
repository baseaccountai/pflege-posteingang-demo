"""Deterministic stand-in for tests and the e2e run without a Mistral key.

Each word is hashed to one of the 1024 positions ("hashing trick"); the vector is normalised.
Texts that share words therefore really are similar - enough to test retrieval end to end
without a model. Not meaningful beyond shared words (no synonyms).
"""

import hashlib
import math
import re

from app.providers.embeddings.base import DIMENSION

WORD = re.compile(r"\w+")


class FakeEmbeddings:
    model_name = "fake-embed (Testattrappe)"
    dimension = DIMENSION

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self.vector(text) for text in texts]

    @staticmethod
    def vector(text: str) -> list[float]:
        values = [0.0] * DIMENSION
        for word in WORD.findall(text.casefold()):
            digest = hashlib.sha256(word.encode()).digest()
            values[int.from_bytes(digest[:4], "big") % DIMENSION] += 1.0
        length = math.sqrt(sum(v * v for v in values))
        if length == 0:  # no words at all: a fixed unit vector
            return [1.0] + [0.0] * (DIMENSION - 1)
        return [v / length for v in values]
