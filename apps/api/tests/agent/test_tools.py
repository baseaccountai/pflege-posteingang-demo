"""F08-AC4: the agent has exactly five tools, and every call is checked before it runs.

These tests need no database: a refused call never reaches it. What the tools return
under RLS is tested in tests/rls/test_agent_tools.py.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.agent.tools import TOOLS, ToolContext, ToolRefused, call_tool, tool_schemas
from app.auth.principal import Principal

pytestmark = pytest.mark.anyio

AGENT = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1",
    actor_type="agent",
)  # fmt: skip
HUMAN = Principal(sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft")
RESIDENT = "11111111-1111-1111-1111-111111111111"


def berlin_today():
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


class Untouchable:
    """Stands in for database and gateway: any use means the check let a call through."""

    def __getattr__(self, name):
        raise AssertionError(f"a refused call reached {name}")


def context(principal: Principal = AGENT) -> ToolContext:
    return ToolContext(
        db=Untouchable(), principal=principal, gateway=Untouchable(), min_similarity=0.5
    )


def test_the_agent_has_exactly_the_five_tools_of_the_spec():
    assert set(TOOLS) == {
        "dokumente_durchsuchen",
        "bewohnerakte_lesen",
        "medikation_abgleichen",
        "wiedervorlagen_auflisten",
        "wiedervorlage_vorschlagen",
    }


def test_the_schemas_for_function_calling_name_every_tool_with_its_arguments():
    schemas = {s["function"]["name"]: s for s in tool_schemas()}
    assert set(schemas) == set(TOOLS)
    proposal = schemas["wiedervorlage_vorschlagen"]
    assert proposal["type"] == "function"
    assert proposal["function"]["description"]
    parameters = proposal["function"]["parameters"]
    assert set(parameters["properties"]) == {"bewohner_id", "titel", "faellig_am"}
    assert set(parameters["required"]) == {"bewohner_id", "titel"}
    assert parameters["additionalProperties"] is False


async def test_an_unknown_tool_is_refused():
    with pytest.raises(ToolRefused) as refused:
        await call_tool(context(), "medikation_aendern", {"dokument_id": RESIDENT})
    assert refused.value.reason == "unknown_tool"


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("bewohnerakte_lesen", {"bewohner_id": "kein-uuid"}),
        ("bewohnerakte_lesen", {}),
        ("bewohnerakte_lesen", {"bewohner_id": RESIDENT, "ward_id": "wb2"}),  # extra argument
        ("dokumente_durchsuchen", {"frage": ""}),
        ("dokumente_durchsuchen", {"frage": "x" * 501}),
        ("medikation_abgleichen", {"dokument_id": "1; drop table"}),
        ("wiedervorlagen_auflisten", {"bewohner_id": 42}),
        ("wiedervorlage_vorschlagen", {"bewohner_id": RESIDENT, "titel": ""}),
        ("wiedervorlage_vorschlagen", {"bewohner_id": RESIDENT, "titel": "   "}),
        ("wiedervorlage_vorschlagen", {"bewohner_id": RESIDENT, "titel": "x" * 121}),
        (
            "wiedervorlage_vorschlagen",
            {"bewohner_id": RESIDENT, "titel": "Kontrolle", "faellig_am": "morgen"},
        ),
    ],
)
async def test_invalid_arguments_are_refused_before_anything_runs(name, arguments):
    with pytest.raises(ToolRefused) as refused:
        await call_tool(context(), name, arguments)
    assert refused.value.reason == "invalid_arguments"


async def test_a_proposal_cannot_be_due_in_the_past():
    yesterday = (berlin_today() - timedelta(days=1)).isoformat()
    with pytest.raises(ToolRefused) as refused:
        await call_tool(
            context(),
            "wiedervorlage_vorschlagen",
            {"bewohner_id": RESIDENT, "titel": "Kontrolle", "faellig_am": yesterday},
        )
    assert refused.value.reason == "invalid_arguments"


async def test_arguments_that_are_not_an_object_are_refused():
    with pytest.raises(ToolRefused) as refused:
        await call_tool(context(), "bewohnerakte_lesen", ["11111111"])
    assert refused.value.reason == "invalid_arguments"


async def test_tools_run_only_with_the_agent_principal():
    # A human principal would let the agent write like a human: never run the tools with it.
    with pytest.raises(ToolRefused) as refused:
        await call_tool(context(HUMAN), "bewohnerakte_lesen", {"bewohner_id": RESIDENT})
    assert refused.value.reason == "not_an_agent"
