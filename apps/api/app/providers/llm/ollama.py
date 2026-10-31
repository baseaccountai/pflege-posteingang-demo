"""Ollama (local model, F03-AC13): same interface, schema passed as `format`.

Stage 1: adapter only; the local stack with a model follows in phase 8.
"""

import httpx

from app.providers.llm._json import json_object
from app.providers.llm.base import ChatTurn, LlmUnavailable, Message, ToolCall

TIMEOUT_SECONDS = 120  # local models on a laptop are slow


class OllamaLlm:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model_name = model

    async def structured(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        body = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "format": schema,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0},
        }
        message = await self._chat(body)
        return json_object(message.get("content"))

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict], max_tokens: int
    ) -> ChatTurn:
        body = {
            "model": self.model_name,
            "messages": [_to_ollama(m) for m in messages],
            "tools": tools,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0},
        }
        message = await self._chat(body)
        try:
            # Ollama gives the calls no id: they are numbered within the turn.
            calls = [
                ToolCall(f"call_{n}", c["function"]["name"], c["function"].get("arguments"))
                for n, c in enumerate(message.get("tool_calls") or [], start=1)
            ]
            return ChatTurn(content=message.get("content") or "", tool_calls=calls)
        except (KeyError, TypeError, AttributeError) as error:
            raise LlmUnavailable(f"Ollama failed: {type(error).__name__}") from None

    async def _chat(self, body: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=body)
            response.raise_for_status()
            message = response.json()["message"]
            if not isinstance(message, dict):
                raise TypeError("message is not an object")
            return message
        except httpx.HTTPStatusError as error:
            raise LlmUnavailable(f"Ollama answered {error.response.status_code}") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise LlmUnavailable(f"Ollama failed: {type(error).__name__}") from None


def _to_ollama(message: Message) -> dict:
    """Neutral message -> Ollama: arguments as an object, a tool result names its tool."""
    if message["role"] == "tool":
        return {"role": "tool", "content": message["content"], "tool_name": message["name"]}
    if message["role"] == "assistant" and message.get("tool_calls"):
        return {
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": [
                {"function": {"name": call.name, "arguments": call.arguments}}
                for call in message["tool_calls"]
            ],
        }
    return dict(message)
