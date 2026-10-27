"""LLM interface (F03, F05). Providers are exchangeable by configuration (F03-AC13)."""

from typing import Protocol


class LlmUnavailable(Exception):
    """Provider not reachable, timed out or answered with an error -> failed/llm_unavailable."""


class LlmInvalidOutput(Exception):
    """The model answered, but not with a JSON object (the caller may ask once more)."""


class LlmProvider(Protocol):
    model_name: str

    async def structured(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        """Answer as a JSON object following `schema` (the caller validates it again)."""
        ...
