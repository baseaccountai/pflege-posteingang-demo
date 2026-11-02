"""F10-AC16: /health/models says whether the AI provider answers and accepts the key - without
calling a model, and asking the provider at most once a minute."""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers.llm.reachability import ProviderCheck, create_provider_check

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_the_answer_is_kept_for_a_minute():
    answers, asked = [True, False], []

    async def probe() -> bool:
        asked.append(1)
        return answers.pop(0)

    clock = Clock()
    check = ProviderCheck(probe, clock=clock)
    assert await check.status() == "ok"
    clock.now += 59
    assert await check.status() == "ok" and len(asked) == 1  # not asked again
    clock.now += 2
    assert await check.status() == "unavailable" and len(asked) == 2


async def test_an_error_while_asking_means_unavailable():
    async def probe() -> bool:
        raise OSError("no route")

    assert await ProviderCheck(probe).status() == "unavailable"


async def test_mistral_is_asked_for_its_model_list_with_the_key():
    seen = {}

    async def fetch(url: str, headers: dict) -> int:
        seen.update(url=url, auth=headers.get("Authorization"))
        return 200

    settings = Settings(llm_provider="mistral", mistral_api_key="k-test")
    assert await create_provider_check(settings, fetch).status() == "ok"
    assert seen == {"url": "https://api.mistral.ai/v1/models", "auth": "Bearer k-test"}


@pytest.mark.parametrize("code", [401, 429, 500])
async def test_a_refused_key_or_an_outage_is_unavailable(code):
    async def fetch(url: str, headers: dict) -> int:
        return code

    settings = Settings(llm_provider="mistral", mistral_api_key="k-test")
    assert await create_provider_check(settings, fetch).status() == "unavailable"


async def test_without_a_key_mistral_is_unavailable_and_not_asked():
    async def fetch(url: str, headers: dict) -> int:
        raise AssertionError("must not ask without a key")

    settings = Settings(llm_provider="mistral", mistral_api_key="")
    assert await create_provider_check(settings, fetch).status() == "unavailable"


async def test_ollama_is_asked_for_its_local_models():
    seen = []

    async def fetch(url: str, headers: dict) -> int:
        seen.append(url)
        return 200

    settings = Settings(llm_provider="ollama", ollama_base_url="http://localhost:11434")
    assert await create_provider_check(settings, fetch).status() == "ok"
    assert seen == ["http://localhost:11434/api/tags"]


def test_the_endpoint_is_public_and_names_only_the_state():
    async def down(url: str, headers: dict) -> int:
        return 503

    settings = Settings(llm_provider="mistral", mistral_api_key="k-test")
    app = create_app(settings)
    app.state.provider_check = create_provider_check(settings, down)  # kept by the lifespan
    with TestClient(app) as api:
        response = api.get("/health/models")
    assert response.status_code == 200
    assert response.json() == {"llm": "unavailable"}
