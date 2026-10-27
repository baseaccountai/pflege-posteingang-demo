"""LLM interface (F03). Only the error type is needed by the F02 pipeline so far."""


class LlmUnavailable(Exception):
    """Provider not reachable, timed out or answered with an error -> failed/llm_unavailable."""
