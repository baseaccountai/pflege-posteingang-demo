"""F11-AC13: the settings `make up-local` gives the API are accepted by it - and the smoke
probe on the host waits as long for Ollama as the API does (Codex review phase 8).

The values are read from infra/local-stack.sh and infra/smoke-local.sh (fixed `-e NAME=value`
pairs and `NAME=value` assignments); values built from shell variables are left out.
"""

import re
from pathlib import Path

from app.config import Settings

INFRA = Path(__file__).parents[4] / "infra"
FIXED = re.compile(r"\b([A-Z][A-Z0-9_]+)=([0-9A-Za-z._:/-]+)(?=\s|\)|$)")


def fixed_values(script: str) -> dict[str, str]:
    lines = (INFRA / script).read_text().splitlines()
    code = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
    return dict(FIXED.findall(code))


def test_the_api_accepts_the_local_settings():
    values = fixed_values("local-stack.sh")
    names = (
        "LLM_PROVIDER",
        "OLLAMA_TIMEOUT_SECONDS",
        "AGENT_MAX_SECONDS",
        "AGENT_TOKEN_MAX_SECONDS",
        "PIPELINE_STEP_SECONDS",
    )
    local = {name.lower(): values[name] for name in names}
    settings = Settings(**local)  # raises if a limit is refused
    # The agent never works longer than its token is valid (ADR 0012).
    assert settings.agent_max_seconds <= settings.agent_token_max_seconds


def test_the_smoke_probe_waits_as_long_for_ollama_as_the_api():
    api = fixed_values("local-stack.sh")["OLLAMA_TIMEOUT_SECONDS"]
    probe = fixed_values("smoke-local.sh").get("OLLAMA_TIMEOUT_SECONDS")
    assert probe == api
