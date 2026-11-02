"""F11-AC18: with LLM_PROVIDER=ollama every model role runs on the own machine.

Field suggestion, answers and agent (llm), the injection checker (guard) and the embeddings
all go to Ollama - also when a MISTRAL_API_KEY happens to be set, so no text leaves the
computer by mistake ("im lokalen Modus sieht kein fremdes Modell die Daten").
"""

import pytest

from app.config import Settings
from app.privacy.gateway import create_gateway
from app.providers.embeddings.ollama import OllamaEmbeddings
from app.providers.llm.ollama import OllamaLlm


def test_every_model_role_is_ollama_even_with_a_mistral_key():
    settings = Settings(llm_provider="ollama", mistral_api_key="set-by-mistake")
    gateway = create_gateway(settings, db=None)
    assert isinstance(gateway.llm, OllamaLlm)
    assert isinstance(gateway.guard, OllamaLlm)
    assert isinstance(gateway.embeddings, OllamaEmbeddings)
    assert gateway.llm.model_name == gateway.guard.model_name == "qwen3:8b"
    assert gateway.embeddings.model_name == "bge-m3"


def test_the_ollama_timeout_is_two_minutes_unless_the_local_mode_sets_more():
    # Measured 01.11.2026: qwen3:8b on the applicant's laptop writes ~1.2 tokens/s, so
    # `make up-local` sets OLLAMA_TIMEOUT_SECONDS; the default stays as before.
    for seconds, expected in [(None, 120), (600, 600)]:
        extra = {} if seconds is None else {"ollama_timeout_seconds": seconds}
        gateway = create_gateway(Settings(llm_provider="ollama", **extra), db=None)
        assert gateway.llm.timeout == gateway.guard.timeout == expected
        assert gateway.embeddings.timeout == expected


def test_the_pipeline_step_limit_is_five_minutes_unless_the_local_mode_sets_more(monkeypatch):
    assert Settings().pipeline_step_seconds == 300  # F02-AC8, public demo
    monkeypatch.setenv("PIPELINE_STEP_SECONDS", "1800")  # set by `make up-local`
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert Settings().pipeline_step_seconds == 1800


# --- longer limits only in the local mode (Codex review phase 8) -----------------------------


@pytest.mark.parametrize("provider", ["mistral", "fake"])
@pytest.mark.parametrize(
    "longer",
    [
        {"agent_max_seconds": 61},
        {"pipeline_step_seconds": 301},
        {"agent_token_max_seconds": 301},
    ],
    ids=["agent", "pipeline-step", "agent-token"],
)
def test_longer_local_limits_are_refused_outside_the_local_mode(provider, longer):
    # Local env variables copied into Vercel by mistake must not stretch the public limits.
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="LLM_PROVIDER=ollama"):
        Settings(llm_provider=provider, **longer)


def test_the_local_mode_may_set_ten_minutes_for_the_agent_and_its_token():
    settings = Settings(llm_provider="ollama", agent_max_seconds=600, agent_token_max_seconds=600)
    assert (settings.agent_max_seconds, settings.agent_token_max_seconds) == (600, 600)


def test_a_task_may_not_outlast_the_agent_token():
    # Codex review phase 8: 600 s for the task, 300 s for the token - the agent kept working
    # after its delegation had expired.
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="AGENT_TOKEN_MAX_SECONDS"):
        Settings(llm_provider="ollama", agent_max_seconds=600, agent_token_max_seconds=300)
