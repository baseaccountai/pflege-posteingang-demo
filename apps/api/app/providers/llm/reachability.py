"""Is the AI provider reachable? (F10-AC16, `GET /health/models`)

A failed request in the app does not tell whether the provider is down or the check judged
badly. This answers the first question without calling a model: Mistral lists its models
(no tokens, no quota of ours), Ollama its local models. The endpoint is public, so the
answer is kept for a minute - however often it is asked, the provider sees at most one
request per minute from here. The key is sent only to the provider and never shown.
"""

import time
from collections.abc import Awaitable, Callable

import httpx

from app.config import Settings

MODELS_URL = "https://api.mistral.ai/v1/models"
KEEP_SECONDS = 60
TIMEOUT_SECONDS = 5

Fetch = Callable[[str, dict], Awaitable[int]]  # (url, headers) -> HTTP status


async def http_status(url: str, headers: dict) -> int:
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        return (await client.get(url, headers=headers)).status_code


class ProviderCheck:
    def __init__(
        self,
        probe: Callable[[], Awaitable[bool]],
        clock: Callable[[], float] = time.monotonic,
    ):
        self._probe = probe
        self._clock = clock
        self._state: str | None = None
        self._asked_at = 0.0

    async def status(self) -> str:
        """Either "ok" or "unavailable". Asks the provider only if the last answer is older
        than a minute. No lock: a serverless instance may run each request in its own event
        loop; at worst a few requests arriving in the same moment ask once each."""
        if self._state is None or self._clock() - self._asked_at >= KEEP_SECONDS:
            self._asked_at = self._clock()  # set first: requests meanwhile use the old state
            try:
                reachable = await self._probe()
            except Exception:  # any failure to ask means: not reachable
                reachable = False
            self._state = "ok" if reachable else "unavailable"
        return self._state or "unavailable"


def create_provider_check(settings: Settings, fetch: Fetch = http_status) -> ProviderCheck:
    async def probe() -> bool:
        if settings.llm_provider == "mistral":
            if not settings.mistral_api_key:
                return False
            headers = {"Authorization": f"Bearer {settings.mistral_api_key}"}
            return await fetch(MODELS_URL, headers) == 200
        if settings.llm_provider == "ollama":
            return await fetch(f"{settings.ollama_base_url.rstrip('/')}/api/tags", {}) == 200
        return True  # the fake model of the tests is always there

    return ProviderCheck(probe)
