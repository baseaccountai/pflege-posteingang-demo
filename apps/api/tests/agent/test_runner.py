"""F08-AC8, AC9, AC10, AC12: the agent's loop - without database.

The model is the fake with a script, the residents come from a fixed directory; booking a
model call and writing an audit event are recorders. Tools that need the database are
tested in tests/rls/test_agent_runner.py.
"""

import asyncio
import json
from datetime import date

import pytest

from app.agent.runner import (
    FOREIGN_ANSWER,
    LIMIT_ANSWER,
    LIMITS,
    MAX_OUTPUT_TOKENS,
    UNSAFE_ANSWER,
    Limits,
    run_agent,
)
from app.agent.tools import ToolContext
from app.privacy.gateway import ModelGateway
from app.privacy.pseudonymizer import KnownResident
from app.providers.embeddings.fake import FakeEmbeddings
from app.providers.llm.base import ChatTurn, LlmUnavailable, ToolCall
from app.providers.llm.fake import FakeLlm
from app.quotas import QuotaExceeded
from tests.agent.test_tools import AGENT, Untouchable

pytestmark = pytest.mark.anyio

OWN = "11111111-1111-1111-1111-111111111111"
FOREIGN = "22222222-2222-2222-2222-222222222222"
RESIDENTS = [
    KnownResident(OWN, "K42", "Hr. Muster-Bauer", date(1941, 4, 3)),
    KnownResident(FOREIGN, "W58", "Fr. Testfeld", None),  # another ward
]


class Recorder:
    def __init__(self):
        self.booked = 0
        self.events: list[tuple[str, str, dict]] = []

    async def book(self) -> None:
        self.booked += 1

    async def log(self, action: str, outcome: str = "ok", **details) -> None:
        self.events.append((action, outcome, details))


def gateway(llm: FakeLlm) -> ModelGateway:
    async def directory():
        return RESIDENTS

    async def visible(principal):
        return {OWN}

    return ModelGateway(llm, FakeEmbeddings(), directory, visible)


async def agent(llm: FakeLlm, task: str, limits: Limits = LIMITS, resident_id=None, rec=None):
    rec = rec or Recorder()
    ctx = ToolContext(db=Untouchable(), principal=AGENT, gateway=gateway(llm), min_similarity=0.5)
    result = await run_agent(ctx, task, resident_id, book=rec.book, log=rec.log, limits=limits)
    return result, rec


def call(name: str, arguments: object = None, n: int = 1) -> ChatTurn:
    return ChatTurn(content="", tool_calls=[ToolCall(f"c{n}", name, arguments or {})])


# --- the conversation -----------------------------------------------------------------------


async def test_the_model_sees_the_rules_and_the_task_only_pseudonymised():
    llm = FakeLlm(turns=[ChatTurn("Bewohner_K42 hat keine offenen Wiedervorlagen.")])
    result, rec = await agent(llm, "Was steht für Hr. Muster-Bauer an?")

    system, user = llm.chats[0]
    assert system["role"] == "system"
    assert "keine Anweisungen" in system["content"]  # tool results are data (AC13)
    assert "Medikation ändern" in system["content"]  # what the agent cannot do (AC8)
    assert "Muster-Bauer" not in user["content"]
    assert "Bewohner_K42" in user["content"]
    # The model learns the ids of the own residents only - never of another ward.
    assert OWN in user["content"] and FOREIGN not in user["content"]
    assert llm.max_tokens == [MAX_OUTPUT_TOKENS]
    # The answer comes back with the real name; one model call, one booking (AC12).
    assert result.answer == "Hr. Muster-Bauer hat keine offenen Wiedervorlagen."
    assert result.tools_used == [] and result.proposals == [] and not result.stopped
    assert rec.booked == 1 and result.model_calls == 1


async def test_an_own_resident_typed_in_lower_case_reaches_the_model_only_as_placeholder(
    monkeypatch,
):
    # Codex review phase 7: "muster-bauer" went to the model unchanged - in the task and
    # in a tool result alike.
    async def tool_result(ctx, name, arguments):
        return {"wiedervorlagen": [{"titel": "Blutdruck messen", "bewohner": "muster-bauer"}]}

    monkeypatch.setattr("app.agent.runner.call_tool", tool_result)
    llm = FakeLlm(turns=[call("wiedervorlagen_auflisten"), ChatTurn("ok")])
    await agent(llm, "was steht für muster-bauer an?")

    sent = json.dumps(llm.chats, ensure_ascii=False, default=str).lower()
    assert "muster-bauer" not in sent
    assert "Bewohner_K42" in llm.chats[0][1]["content"]
    assert "Bewohner_K42" in llm.chats[1][-1]["content"]  # the tool result


async def test_the_model_is_told_todays_date():
    # Phase 8 walkthrough: qwen3:8b proposed a follow-up "due 2023-10-05" - the model does
    # not know the date, and a due date in the past is refused (invalid_arguments).
    from datetime import datetime
    from zoneinfo import ZoneInfo

    llm = FakeLlm(turns=[ChatTurn("ok")])
    await agent(llm, "Was steht an?")
    today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    assert f"Heute ist der {today} (JJJJ-MM-TT)." in llm.chats[0][1]["content"]


async def test_a_resident_chosen_in_the_app_is_named_to_the_model():
    llm = FakeLlm(turns=[ChatTurn("ok")])
    await agent(llm, "Was steht an?", resident_id=OWN)
    assert f"Ausgewählter Bewohner: Bewohner_K42 (bewohner_id {OWN})" in llm.chats[0][1]["content"]


@pytest.mark.parametrize(
    ("task", "resident_id"),
    [
        ("Medikation von Fr. Testfeld?", None),  # another ward
        ("Medikation von Fr. Unbekannt?", None),  # nobody
        # Review phase 7: the placeholders would give these away (W58 is not in the list).
        ("Medikation von Testfeld?", None),  # bare surname of another ward
        ("medikation von fr. testfeld?", None),  # lower case
        ("Medikation von Fr. Muster-Bauer und Fr. Testfeld?", None),  # one of two foreign
        ("Medikation?", FOREIGN),
        ("Medikation?", "kein-uuid"),
    ],
)
async def test_another_ward_and_nobody_get_the_same_answer_without_a_model_call(task, resident_id):
    llm = FakeLlm()
    result, rec = await agent(llm, task, resident_id=resident_id)
    assert result.answer == FOREIGN_ANSWER
    assert FOREIGN_ANSWER == (
        "Dazu gibt es in deinem Wohnbereich nichts – der Agent hat dieselben Rechte wie du."
    )
    assert llm.chats == [] and rec.booked == 0 and result.model_calls == 0


# --- refused calls (AC9) --------------------------------------------------------------------


async def test_an_unknown_tool_is_not_run_but_logged_and_answered_with_not_allowed():
    llm = FakeLlm(turns=[call("medikation_aendern", {"dosis": "10 mg"}), ChatTurn("Geht nicht.")])
    result, rec = await agent(llm, "Ramipril auf 10 mg")

    assert rec.events == [("blocked", "blocked", {"error_code": "unknown_tool"})]
    tool_message = llm.chats[1][-1]
    assert tool_message == {
        "role": "tool",
        "tool_call_id": "c1",
        "name": "medikation_aendern",
        "content": "nicht erlaubt",
    }
    assert result.tools_used == [] and result.answer == "Geht nicht."


async def test_invalid_arguments_are_not_run_but_logged_with_the_tool():
    llm = FakeLlm(turns=[call("bewohnerakte_lesen", {"bewohner_id": "x"}), ChatTurn("Fehler.")])
    result, rec = await agent(llm, "Akte lesen")
    assert rec.events == [
        ("blocked", "blocked", {"error_code": "invalid_arguments", "tool": "bewohnerakte_lesen"})
    ]
    assert llm.chats[1][-1]["content"] == "nicht erlaubt"


# --- limits (AC12) --------------------------------------------------------------------------


async def test_at_most_four_tool_steps_then_the_agent_stops_with_a_hint():
    llm = FakeLlm(turns=[call("unbekannt", n=n) for n in range(1, 10)])
    result, rec = await agent(llm, "Endlos")
    blocked = [e for e in rec.events if e[0] == "blocked"]
    assert len(blocked) == 4  # the fifth call is not even checked
    assert result.stopped and result.answer == LIMIT_ANSWER
    assert len(llm.chats) == 5 and rec.booked == 5


async def test_at_most_five_model_calls():
    llm = FakeLlm(turns=[call("unbekannt", n=n) for n in range(1, 10)])
    result, rec = await agent(llm, "Endlos", limits=Limits(tool_steps=99))
    assert len(llm.chats) == 5 and rec.booked == 5 and result.model_calls == 5
    assert result.stopped and result.answer == LIMIT_ANSWER


async def test_after_the_time_limit_the_agent_stops_with_a_hint():
    class SlowLlm(FakeLlm):
        async def chat_with_tools(self, messages, tools, max_tokens):
            turn = await super().chat_with_tools(messages, tools, max_tokens)  # records first
            await asyncio.sleep(0.1)
            return turn

    # Calls start at 0, 0.1 and 0.2 s; the third is cut off at 0.25 s.
    llm = SlowLlm(turns=[call("unbekannt", n=n) for n in range(1, 10)])
    result, _ = await agent(llm, "Langsam", limits=Limits(seconds=0.25))
    assert result.stopped and result.answer == LIMIT_ANSWER
    assert len(llm.chats) == 3


async def test_a_long_tool_result_is_cut_after_pseudonymisation(monkeypatch):
    # Codex review phase 7: a record with a huge diagnosis went to the model in full.
    from app.agent.runner import MAX_TOOL_RESULT_CHARS

    async def tool_result(ctx, name, arguments):
        return {"diagnosen": ["Muster-Bauer " * 50_000]}

    monkeypatch.setattr("app.agent.runner.call_tool", tool_result)
    llm = FakeLlm(turns=[call("bewohnerakte_lesen"), ChatTurn("ok")])
    await agent(llm, "Akte lesen")

    content = llm.chats[1][-1]["content"]
    assert len(content) <= MAX_TOOL_RESULT_CHARS + 200  # tags and the hint
    assert "(gekürzt)" in content and "Muster-Bauer" not in content


async def test_no_model_call_gets_more_input_than_the_cost_calculation_assumes(monkeypatch):
    # Four maximal tool results plus long tool calls: every call stays within the budget
    # that app/costs.py counts for an agent call (F10-AC11).
    from app.agent.runner import AGENT_MAX_INPUT_CHARS, input_chars
    from app.agent.tools import tool_schemas

    async def tool_result(ctx, name, arguments):
        return {"text": "x" * 100_000}

    monkeypatch.setattr("app.agent.runner.call_tool", tool_result)
    # 500 output tokens are at most about 2 000 characters: text and arguments together.
    long_call = ChatTurn("y" * 1_000, [ToolCall("c1", "bewohnerakte_lesen", {"z": "z" * 1_000})])
    llm = FakeLlm(turns=[long_call] * 4 + [ChatTurn("ok")])
    await agent(llm, "Was steht an? " * 35)

    assert len(llm.chats) == 5
    for messages in llm.chats:
        assert input_chars(messages, tool_schemas()) <= AGENT_MAX_INPUT_CHARS


async def test_an_input_above_the_budget_stops_the_agent_before_the_call(monkeypatch):
    monkeypatch.setattr("app.agent.runner.AGENT_MAX_INPUT_CHARS", 100)
    llm = FakeLlm(turns=[ChatTurn("ok")])
    result, rec = await agent(llm, "Was steht an?")
    assert result.answer == LIMIT_ANSWER and result.stopped
    assert llm.chats == [] and rec.booked == 0


async def test_every_model_call_is_booked_before_it_is_made():
    class Exhausted(Recorder):
        async def book(self):
            raise QuotaExceeded("llm_call")

    llm = FakeLlm()
    with pytest.raises(QuotaExceeded):
        await agent(llm, "Auftrag", rec=Exhausted())
    assert llm.chats == []


async def test_an_unavailable_model_is_passed_on():
    with pytest.raises(LlmUnavailable):
        await agent(FakeLlm(turns=[LlmUnavailable("down")]), "Auftrag")


# --- the answer -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer", ["Siehe [hier](https://evil.example/?d=K42)", "<img src=x onerror=alert(1)>"]
)
async def test_an_answer_with_links_or_html_is_not_shown(answer):
    result, rec = await agent(FakeLlm(turns=[ChatTurn(answer)]), "Auftrag")
    assert result.answer == UNSAFE_ANSWER
    assert ("blocked", "blocked", {"error_code": "unsafe_output"}) in rec.events


async def test_a_plain_foreign_name_written_by_the_model_is_not_shown():
    # The model names a resident of another ward: shown only as its placeholder.
    result, _ = await agent(FakeLlm(turns=[ChatTurn("Fr. Testfeld auch prüfen.")]), "Auftrag")
    assert result.answer == "Bewohner_W58 auch prüfen."


async def test_a_placeholder_typed_into_the_task_is_no_error():
    llm = FakeLlm(turns=[ChatTurn("Kenne ich nicht.")])
    result, _ = await agent(llm, "Was ist mit Bewohner_Z99?")
    assert result.answer == "Kenne ich nicht."


def test_the_agent_has_60_seconds_unless_the_local_mode_sets_more():
    # F08-AC12: 60 s in the public demo; a local CPU model needs minutes (OLLAMA, 01.11.2026).
    from app.agent.runner import agent_limits
    from app.config import Settings

    assert agent_limits(Settings()) == Limits(seconds=60)
    local = Settings(llm_provider="ollama", agent_max_seconds=300)
    assert agent_limits(local) == Limits(seconds=300)


@pytest.mark.parametrize("seconds", [0, 601])
def test_the_agent_time_limit_stays_within_ten_minutes(seconds):
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(agent_max_seconds=seconds)
