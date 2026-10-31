"""F08-AC4, AC12: Function Calling for the agent - the same call for Mistral, Ollama and the
fake. The messages use one neutral form; each adapter translates it to its API."""

import json

import httpx
import pytest
import respx

from app.providers.llm.base import ChatTurn, LlmUnavailable, ToolCall
from app.providers.llm.fake import FakeLlm
from app.providers.llm.mistral import CHAT_URL, MistralLlm
from app.providers.llm.ollama import OllamaLlm

pytestmark = pytest.mark.anyio

KEY = "test-key-not-real"
OLLAMA = "http://ollama:11434/api/chat"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bewohnerakte_lesen",
            "description": "Liest die Akte.",
            "parameters": {"type": "object", "properties": {"bewohner_id": {"type": "string"}}},
        },
    }
]
# A conversation after one tool step: the neutral form every adapter receives.
MESSAGES = [
    {"role": "system", "content": "System"},
    {"role": "user", "content": "Auftrag"},
    {
        "role": "assistant",
        "content": "",
        "tool_calls": [ToolCall("c1", "bewohnerakte_lesen", {"bewohner_id": "r1"})],
    },
    {"role": "tool", "tool_call_id": "c1", "name": "bewohnerakte_lesen", "content": "{}"},
]


def mistral_answer(message: dict) -> dict:
    return {"choices": [{"index": 0, "message": {"role": "assistant", **message}}]}


# --- Mistral --------------------------------------------------------------------------------


@respx.mock
async def test_mistral_sends_tools_and_the_conversation_in_its_format():
    route = respx.post(CHAT_URL).mock(
        return_value=httpx.Response(200, json=mistral_answer({"content": "Fertig."}))
    )
    turn = await MistralLlm(KEY, "mistral-small-latest").chat_with_tools(MESSAGES, TOOLS, 400)

    assert turn == ChatTurn(content="Fertig.", tool_calls=[])
    body = json.loads(route.calls.last.request.content)
    assert body["tools"] == TOOLS
    assert body["tool_choice"] == "auto"
    assert body["parallel_tool_calls"] is False  # one step at a time: the limits count steps
    assert body["max_tokens"] == 400 and body["temperature"] == 0
    assert body["messages"][2] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "bewohnerakte_lesen", "arguments": '{"bewohner_id": "r1"}'},
            }
        ],
    }
    assert body["messages"][3] == {
        "role": "tool",
        "tool_call_id": "c1",
        "name": "bewohnerakte_lesen",
        "content": "{}",
    }


@respx.mock
async def test_mistral_tool_calls_come_back_with_parsed_arguments():
    call = {"id": "abc123XYZ", "type": "function", "function": {"name": "x", "arguments": "{}"}}
    broken = {"id": "def456UVW", "function": {"name": "y", "arguments": "kein json"}}
    respx.post(CHAT_URL).mock(
        return_value=httpx.Response(
            200, json=mistral_answer({"content": None, "tool_calls": [call, broken]})
        )
    )
    turn = await MistralLlm(KEY, "m").chat_with_tools(MESSAGES[:2], TOOLS, 100)
    # Arguments that are no JSON stay a string: the tool check refuses them (AC9).
    assert turn == ChatTurn(
        content="",
        tool_calls=[ToolCall("abc123XYZ", "x", {}), ToolCall("def456UVW", "y", "kein json")],
    )


@respx.mock
@pytest.mark.parametrize(
    "answer", [httpx.Response(500), httpx.Response(200, json={})], ids=["500", "wrong-shape"]
)
async def test_mistral_tool_errors_become_llm_unavailable_without_the_key(answer):
    respx.post(CHAT_URL).mock(return_value=answer)
    with pytest.raises(LlmUnavailable) as error:
        await MistralLlm(KEY, "m").chat_with_tools(MESSAGES[:2], TOOLS, 100)
    assert KEY not in str(error.value)


async def test_mistral_without_key_makes_no_tool_call():
    with pytest.raises(LlmUnavailable):
        await MistralLlm("", "m").chat_with_tools(MESSAGES[:2], TOOLS, 100)


# --- Ollama ---------------------------------------------------------------------------------


@respx.mock
async def test_ollama_sends_tools_and_the_conversation_in_its_format():
    route = respx.post(OLLAMA).mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "x", "arguments": {"a": 1}}}],
                }
            },
        )
    )
    turn = await OllamaLlm("http://ollama:11434", "qwen3:8b").chat_with_tools(MESSAGES, TOOLS, 300)

    # Ollama gives no ids: the adapter numbers the calls of the turn.
    assert turn == ChatTurn(content="", tool_calls=[ToolCall("call_1", "x", {"a": 1})])
    body = json.loads(route.calls.last.request.content)
    assert body["tools"] == TOOLS and body["stream"] is False
    assert body["options"] == {"num_predict": 300, "temperature": 0}
    assert body["messages"][2] == {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": "bewohnerakte_lesen", "arguments": {"bewohner_id": "r1"}}}
        ],
    }
    assert body["messages"][3] == {
        "role": "tool",
        "content": "{}",
        "tool_name": "bewohnerakte_lesen",
    }


@respx.mock
async def test_ollama_not_reachable_is_llm_unavailable_for_tools():
    respx.post(OLLAMA).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(LlmUnavailable):
        await OllamaLlm("http://ollama:11434", "m").chat_with_tools(MESSAGES[:2], TOOLS, 9)


# --- Fake -----------------------------------------------------------------------------------


async def test_the_fake_plays_its_script_and_records_what_it_saw():
    script = [
        ChatTurn(content="", tool_calls=[ToolCall("c1", "bewohnerakte_lesen", {})]),
        LlmUnavailable("down"),
    ]
    llm = FakeLlm(turns=script)
    assert await llm.chat_with_tools(MESSAGES[:2], TOOLS, 100) == script[0]
    with pytest.raises(LlmUnavailable):
        await llm.chat_with_tools(MESSAGES, TOOLS, 100)
    assert llm.chats == [MESSAGES[:2], MESSAGES]
    assert llm.max_tokens == [100, 100]


async def test_the_fake_without_script_answers_without_tools():
    turn = await FakeLlm().chat_with_tools(MESSAGES[:2], TOOLS, 100)
    assert turn.tool_calls == [] and turn.content
