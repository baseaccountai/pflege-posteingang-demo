"""LLM interface (F03, F05, F08). Providers are exchangeable by configuration (F03-AC13)."""

from dataclasses import dataclass, field
from typing import Protocol


class LlmUnavailable(Exception):
    """Provider not reachable, timed out or answered with an error -> failed/llm_unavailable."""


class LlmInvalidOutput(Exception):
    """The model answered, but not with a JSON object (the caller may ask once more)."""


@dataclass(frozen=True)
class ToolCall:
    """One call of a tool the model asks for (F08). `arguments` is the parsed JSON object -
    or, if the model sent no valid JSON, the raw text (the tool check refuses it, AC9)."""

    id: str
    name: str
    arguments: object


@dataclass(frozen=True)
class ChatTurn:
    """The model's turn in the agent's conversation: text, tool calls, or both."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


# The agent's conversation in one neutral form; each adapter translates it to its API:
#   {"role": "system" | "user", "content": str}
#   {"role": "assistant", "content": str, "tool_calls": [ToolCall, ...]}
#   {"role": "tool", "tool_call_id": str, "name": str, "content": str}
Message = dict


class LlmProvider(Protocol):
    model_name: str

    async def structured(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        """Answer as a JSON object following `schema` (the caller validates it again)."""
        ...

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict], max_tokens: int
    ) -> ChatTurn:
        """One model turn with Function Calling (F08); tools as JSON schemas."""
        ...
