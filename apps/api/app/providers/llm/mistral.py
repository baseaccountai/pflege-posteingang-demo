"""Mistral chat completions with a JSON schema as response format (public demo).

The schema is enforced by Mistral ("strict") and checked again by the caller. Every
transport or HTTP failure becomes LlmUnavailable; the API key never appears in messages.
"""

import httpx

from app.providers.llm._json import json_object
from app.providers.llm.base import LlmUnavailable

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
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    CHAT_URL, json=body, headers={"authorization": f"Bearer {self.api_key}"}
                )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as error:
            raise LlmUnavailable(f"Mistral answered {error.response.status_code}") from None
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as error:
            raise LlmUnavailable(f"Mistral chat failed: {type(error).__name__}") from None
        return json_object(content)
