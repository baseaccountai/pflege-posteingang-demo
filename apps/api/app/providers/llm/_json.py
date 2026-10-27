import json

from app.providers.llm.base import LlmInvalidOutput


def json_object(content: str) -> dict:
    """The model's text must be exactly one JSON object; anything else is invalid output."""
    try:
        value = json.loads(content)
    except (TypeError, ValueError) as error:
        raise LlmInvalidOutput("answer is not JSON") from error
    if not isinstance(value, dict):
        raise LlmInvalidOutput("answer is not a JSON object")
    return value
