"""Mistral chat completions with a JSON schema as response format (public demo).

The schema is enforced by Mistral ("strict") and checked again by the caller. Every
transport or HTTP failure becomes LlmUnavailable; the API key never appears in messages.
"""

import json

import httpx

from app.providers.llm._json import json_object
from app.providers.llm.base import ChatTurn, LlmUnavailable, Message, ToolCall

CHAT_URL = "https://api.mistral.ai/v1/chat/completions"
TIMEOUT_SECONDS = 60


class MistralLlm:
    def __init__(self, api_key: str, model: str, timeout: float = TIMEOUT_SECONDS):
        self.api_key = api_key
        self.model_name = model
        self.timeout = timeout

    async def structured(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        if not self.api_key:
            raise LlmUnavailable("MISTRAL_API_KEY is not set")
        body = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "document_suggestion", "schema": schema, "strict": True},
            },
            "max_tokens": max_tokens,
            "temperature": 0,  # extraction, not creativity
        }
        message = await self._chat(body)
        try:
            return json_object(message["content"])
        except (KeyError, TypeError) as error:
            raise LlmUnavailable(f"Mistral chat failed: {type(error).__name__}") from None

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict], max_tokens: int
    ) -> ChatTurn:
        if not self.api_key:
            raise LlmUnavailable("MISTRAL_API_KEY is not set")
        body = {
            "model": self.model_name,
            "messages": [_to_mistral(m) for m in messages],
            "tools": tools,
            "tool_choice": "auto",
            # One tool call per turn: the agent's limits count steps (F08-AC12).
            "parallel_tool_calls": False,
            "max_tokens": max_tokens,
            "temperature": 0,
        }
        message = await self._chat(body)
        try:
            calls = [
                ToolCall(c["id"], c["function"]["name"], _arguments(c["function"]["arguments"]))
                for c in message.get("tool_calls") or []
            ]
            return ChatTurn(content=message.get("content") or "", tool_calls=calls)
        except (KeyError, TypeError, AttributeError) as error:
            raise LlmUnavailable(f"Mistral chat failed: {type(error).__name__}") from None

    async def _chat(self, body: dict) -> dict:
        """The assistant message of one chat completion; every failure is LlmUnavailable."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    CHAT_URL, json=body, headers={"authorization": f"Bearer {self.api_key}"}
                )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
            if not isinstance(message, dict):
                raise TypeError("message is not an object")
            return message
        except httpx.HTTPStatusError as error:
            raise LlmUnavailable(f"Mistral answered {error.response.status_code}") from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
            raise LlmUnavailable(f"Mistral chat failed: {type(error).__name__}") from None


def _to_mistral(message: Message) -> dict:
    """Neutral message -> Mistral: tool calls carry their arguments as a JSON string."""
    if message["role"] != "assistant" or not message.get("tool_calls"):
        return dict(message)
    return {
        "role": "assistant",
        "content": message.get("content") or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in message["tool_calls"]
        ],
    }


def _arguments(text: object) -> object:
    """Mistral sends the arguments as a JSON string; no valid JSON stays the raw text."""
    if not isinstance(text, str):
        return text
    try:
        return json.loads(text)
    except ValueError:
        return text
