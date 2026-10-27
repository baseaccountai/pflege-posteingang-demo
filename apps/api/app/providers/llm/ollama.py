"""Ollama (local model, F03-AC13): same interface, schema passed as `format`.

Stage 1: adapter only; the local stack with a model follows in phase 8.
"""

import httpx

from app.providers.llm._json import json_object
from app.providers.llm.base import LlmUnavailable

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
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(f"{self.base_url}/api/chat", json=body)
            response.raise_for_status()
            content = response.json()["message"]["content"]
        except httpx.HTTPStatusError as error:
            raise LlmUnavailable(f"Ollama answered {error.response.status_code}") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise LlmUnavailable(f"Ollama failed: {type(error).__name__}") from None
        return json_object(content)
