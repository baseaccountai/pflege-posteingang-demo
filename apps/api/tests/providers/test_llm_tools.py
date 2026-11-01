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
    assert body["options"] == {"num_predict": 300, "temperature": 0, "num_ctx": 8192}
    assert body["think"] is False
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


def task(text: str, chosen: bool = False) -> list[dict]:
    """The first two messages as the runner writes them (residents, chosen one, task)."""
    user = "Bewohner in deinem Wohnbereich:\nBewohner_K42 (bewohner_id r1)"
    if chosen:
        user += "\n\nAusgewählter Bewohner: Bewohner_K42 (bewohner_id r1)"
    return [
        {"role": "system", "content": "System"},
        {"role": "user", "content": f"{user}\n\nAuftrag: {text}"},
    ]


@pytest.mark.parametrize(
    ("text", "chosen", "expected"),
    [
        (
            "Wiedervorlage: Blutdruck messen für Bewohner_K42",
            False,
            ToolCall(
                "fake_1",
                "wiedervorlage_vorschlagen",
                {"bewohner_id": "r1", "titel": "Blutdruck messen für Bewohner_K42"},
            ),
        ),
        (
            "Lege eine Wiedervorlage an",
            True,
            ToolCall(
                "fake_1",
                "wiedervorlage_vorschlagen",
                {"bewohner_id": "r1", "titel": "Kontrolle laut Auftrag"},
            ),
        ),
        (
            "Was steht in der Akte?",
            True,
            ToolCall("fake_1", "bewohnerakte_lesen", {"bewohner_id": "r1"}),
        ),
        (
            "Akte von Bewohner_K42?",
            False,
            ToolCall("fake_1", "bewohnerakte_lesen", {"bewohner_id": "r1"}),
        ),
        ("Was ist offen?", False, ToolCall("fake_1", "wiedervorlagen_auflisten", {})),
    ],
)
async def test_the_fake_agent_picks_a_tool_by_simple_rules(text, chosen, expected):
    turn = await FakeLlm().chat_with_tools(task(text, chosen), TOOLS, 100)
    assert turn.tool_calls == [expected]


async def test_the_fake_agent_refuses_what_it_cannot_do_and_offers_a_proposal():
    turn = await FakeLlm().chat_with_tools(task("Ändere die Dosis von Ramipril", True), TOOLS, 100)
    assert turn.tool_calls == []
    assert "kann ich nicht" in turn.content and "Dosis mit Hausarzt klären" in turn.content


@pytest.mark.parametrize(
    ("tool", "content", "answer"),
    [
        (
            "wiedervorlage_vorschlagen",
            '<werkzeugergebnis>{"gefunden": true}</werkzeugergebnis>',
            "vorgeschlagen",
        ),
        (
            "bewohnerakte_lesen",
            '<werkzeugergebnis>{"gefunden": false}</werkzeugergebnis>',
            "dieselben Rechte wie du",
        ),
        (
            "wiedervorlagen_auflisten",
            '<werkzeugergebnis>{"wiedervorlagen": []}</werkzeugergebnis>',
            "dieselben Rechte wie du",
        ),
        (
            "bewohnerakte_lesen",
            '<werkzeugergebnis>{"gefunden": true}</werkzeugergebnis>',
            "Bewohnerakte gelesen",
        ),
        ("medikation_aendern", "nicht erlaubt", "nicht erlaubt"),
    ],
)
async def test_the_fake_agent_answers_after_one_tool_step(tool, content, answer):
    messages = task("x") + [
        {"role": "assistant", "content": "", "tool_calls": [ToolCall("fake_1", tool, {})]},
        {"role": "tool", "tool_call_id": "fake_1", "name": tool, "content": content},
    ]
    turn = await FakeLlm().chat_with_tools(messages, TOOLS, 100)
    assert turn.tool_calls == [] and answer in turn.content
    assert "<" not in turn.content  # no markup in the answer (F07-AC10)
