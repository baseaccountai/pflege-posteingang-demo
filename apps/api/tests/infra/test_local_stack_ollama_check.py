"""F11-AC14: `make up-local` stops before any container starts if Ollama is not running or
a model is missing - and names the command that helps.

The check is `infra/local-stack.sh check-ollama` (also the first step of `up-local`); here it
runs against a stand-in of Ollama's /api/tags.
"""

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[4] / "infra" / "local-stack.sh"


def check(base_url: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SCRIPT), "check-ollama"],
        env={"PATH": "/usr/bin:/bin", "OLLAMA_BASE_URL": base_url},
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture
def ollama():
    """A fake Ollama whose installed models the test sets."""
    installed: list[str] = []

    class Tags(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"models": [{"name": n} for n in installed]}).encode()
            self.send_response(200 if self.path == "/api/tags" else 404)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Tags)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", installed
    server.shutdown()


def test_without_ollama_it_stops_and_says_how_to_start_it():
    result = check("http://127.0.0.1:9")  # nothing listens there
    assert result.returncode != 0
    assert "Ollama läuft nicht" in result.stderr and "ollama serve" in result.stderr


def test_a_missing_model_is_named_with_its_pull_command(ollama):
    url, installed = ollama
    installed.append("qwen3:8b")
    result = check(url)
    assert result.returncode != 0
    assert "ollama pull bge-m3" in result.stderr
    assert "ollama pull qwen3:8b" not in result.stderr


def test_with_both_models_it_passes(ollama):
    url, installed = ollama
    installed += ["qwen3:8b", "bge-m3:latest"]  # Ollama lists the tag ":latest"
    result = check(url)
    assert result.returncode == 0, result.stderr
