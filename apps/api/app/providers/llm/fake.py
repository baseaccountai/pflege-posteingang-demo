"""LLM stand-in for tests and the e2e run without a Mistral key (LLM_PROVIDER=fake).

The rule-based reading of the sample documents follows with the extraction (F03 task 4).
"""


class FakeLlm:
    model_name = "fake-llm (Testattrappe)"

    def __init__(self, answers: list[dict | Exception] | None = None):
        self.answers = list(answers or [])
        self.calls: list[tuple[str, str]] = []

    async def structured(self, system: str, user: str, schema: dict, max_tokens: int) -> dict:
        self.calls.append((system, user))
        if not self.answers:
            return {}
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer
