"""F03-AC13: LLM providers by configuration; adapters against stand-ins of the APIs."""

import json

import httpx
import pytest
import respx

from app.config import Settings
from app.providers.llm import create_llm_provider
from app.providers.llm.base import LlmInvalidOutput, LlmUnavailable
from app.providers.llm.fake import FakeLlm
from app.providers.llm.mistral import CHAT_URL, MistralLlm
from app.providers.llm.ollama import OllamaLlm

pytestmark = pytest.mark.anyio

KEY = "test-key-not-real"
SCHEMA = {"type": "object", "properties": {"doc_type": {"type": "string"}}}


def chat_answer(content: str) -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "model": "mistral-small-2506",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


@pytest.mark.parametrize(
    ("provider", "cls"), [("mistral", MistralLlm), ("ollama", OllamaLlm), ("fake", FakeLlm)]
)
def test_provider_is_chosen_by_configuration(provider, cls):
    llm = create_llm_provider(Settings(llm_provider=provider, mistral_api_key=KEY))
    assert isinstance(llm, cls)
    assert llm.model_name


@respx.mock
async def test_mistral_sends_the_schema_and_returns_the_parsed_answer():
    route = respx.post(CHAT_URL).mock(
        return_value=httpx.Response(200, json=chat_answer('{"doc_type": "arztbrief"}'))
    )
    llm = MistralLlm(KEY, "mistral-small-latest")
    answer = await llm.structured("System", "Nutzer", SCHEMA, max_tokens=1500)

    assert answer == {"doc_type": "arztbrief"}
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert body["model"] == "mistral-small-latest"
    assert body["messages"] == [
        {"role": "system", "content": "System"},
        {"role": "user", "content": "Nutzer"},
    ]
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "document_suggestion", "schema": SCHEMA, "strict": True},
    }
    assert body["max_tokens"] == 1500
    assert body["temperature"] == 0


@respx.mock
@pytest.mark.parametrize("content", ["kein json", "[1, 2]", ""])
async def test_mistral_answer_that_is_no_json_object_is_invalid_output(content):
    respx.post(CHAT_URL).mock(return_value=httpx.Response(200, json=chat_answer(content)))
    with pytest.raises(LlmInvalidOutput):
        await MistralLlm(KEY, "m").structured("s", "u", SCHEMA, max_tokens=10)


@respx.mock
@pytest.mark.parametrize(
    "answer",
    [httpx.Response(500), httpx.Response(429), httpx.Response(401), httpx.Response(200, json={})],
    ids=["500", "rate-limit", "bad-key", "wrong-shape"],
)
async def test_mistral_errors_become_llm_unavailable_without_the_key(answer):
    respx.post(CHAT_URL).mock(return_value=answer)
    with pytest.raises(LlmUnavailable) as error:
        await MistralLlm(KEY, "m").structured("s", "u", SCHEMA, max_tokens=10)
    assert KEY not in str(error.value)


@respx.mock
async def test_mistral_timeout_and_missing_key_become_llm_unavailable():
    route = respx.post(CHAT_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(LlmUnavailable):
        await MistralLlm(KEY, "m").structured("s", "u", SCHEMA, max_tokens=10)
    route.reset()
    with pytest.raises(LlmUnavailable):
        await MistralLlm("", "m").structured("s", "u", SCHEMA, max_tokens=10)
    assert not route.called


@respx.mock
async def test_ollama_sends_the_schema_as_format():
    route = respx.post("http://ollama:11434/api/chat").mock(
        return_value=httpx.Response(
            200, json={"message": {"role": "assistant", "content": '{"doc_type": "sonstiges"}'}}
        )
    )
    answer = await OllamaLlm("http://ollama:11434", "qwen3:8b").structured(
        "s", "u", SCHEMA, max_tokens=99
    )
    assert answer == {"doc_type": "sonstiges"}
    body = json.loads(route.calls.last.request.content)
    assert body["format"] == SCHEMA and body["stream"] is False
    assert body["options"] == {"num_predict": 99, "temperature": 0}


@respx.mock
async def test_ollama_not_reachable_is_llm_unavailable():
    respx.post("http://ollama:11434/api/chat").mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(LlmUnavailable):
        await OllamaLlm("http://ollama:11434", "m").structured("s", "u", SCHEMA, max_tokens=9)
