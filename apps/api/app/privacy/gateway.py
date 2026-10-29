"""The only door to chat and embedding models (F06-AC1, AC10).

Every call of an LLM or an embedding model goes through `ModelGateway`; an architecture
test checks that no other module uses the providers directly. The callers pseudonymise
their text first (they keep the mapping to translate the answer back). The gateway then
checks once more, right before the text leaves: if a resident's name or birth date is
still in it, the call is not made (`PseudonymizationFailed`) - better no answer than plain
names at a cloud provider. OCR is the one exception: it needs the original image.

The directory of residents (names and birth dates of the whole home) is read with the
backend's own role through app.pseudonym_directory() and kept for 60 seconds.
"""

import time
from collections.abc import Awaitable, Callable

from app.auth.principal import Principal
from app.privacy.pseudonymizer import KnownResident, Pseudonymizer
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.llm.base import LlmProvider

DIRECTORY_SECONDS = 60


class PseudonymizationFailed(Exception):
    """A name or birth date of a resident was still in the text for a model."""


class ModelGateway:
    def __init__(
        self,
        llm: LlmProvider,
        embeddings: EmbeddingProvider,
        directory: Callable[[], Awaitable[list[KnownResident]]],
        visible: Callable[[Principal], Awaitable[set[str]]],
    ):
        self.llm = llm
        self.embeddings = embeddings
        self._directory = directory
        self._visible = visible
        self._cached: tuple[float, Pseudonymizer] | None = None

    @property
    def llm_model(self) -> str:
        return self.llm.model_name

    @property
    def embedding_model(self) -> str:
        return self.embeddings.model_name

    async def pseudonymizer(self) -> Pseudonymizer:
        now = time.monotonic()
        if self._cached is None or now - self._cached[0] > DIRECTORY_SECONDS:
            self._cached = (now, Pseudonymizer(await self._directory()))
        return self._cached[1]

    async def visible_residents(self, principal: Principal) -> set[str]:
        """Residents the caller may see (RLS) - only these are translated back (F06-AC8)."""
        return await self._visible(principal)

    async def structured(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        await self._refuse_plain_names(system, user)
        return await self.llm.structured(system, user, schema, max_tokens)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        await self._refuse_plain_names(*texts)
        return await self.embeddings.embed(texts)

    async def _refuse_plain_names(self, *texts: str) -> None:
        pseudonymizer = await self.pseudonymizer()
        if any(pseudonymizer.leaks(text) for text in texts):
            raise PseudonymizationFailed()


def database_directory(db) -> Callable[[], Awaitable[list[KnownResident]]]:
    """Reads the directory with the backend login role, before any role switch."""

    async def load() -> list[KnownResident]:
        async with db.connection() as conn:
            cur = await conn.execute(
                "select resident_id::text, pseudonym, display_name, birth_date"
                " from app.pseudonym_directory()"
            )
            return [KnownResident(*row) for row in await cur.fetchall()]

    return load


def database_visible(db) -> Callable[[Principal], Awaitable[set[str]]]:
    async def visible(principal: Principal) -> set[str]:
        async with db.as_principal(principal) as conn:
            cur = await conn.execute("select id::text from public.residents")
            return {row[0] for row in await cur.fetchall()}

    return visible
