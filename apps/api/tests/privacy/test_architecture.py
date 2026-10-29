"""F06-AC1: only the privacy gateway creates chat and embedding models.

Everything else (routes, pipeline, scripts) gets a ModelGateway and therefore cannot send
a text past the pseudonymisation check. Exceptions and constants of the providers may be
imported anywhere; OCR is not covered (it needs the original image, F06 design).
"""

import ast
from pathlib import Path

API = Path(__file__).parents[2]
FORBIDDEN = {
    "create_llm_provider",
    "create_embedding_provider",
    "MistralLlm",
    "OllamaLlm",
    "FakeLlm",
    "MistralEmbeddings",
    "OllamaEmbeddings",
    "FakeEmbeddings",
}
ALLOWED = {Path("app/privacy/gateway.py")}


def model_imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.providers"):
            names |= {alias.name for alias in node.names} & FORBIDDEN
    return names


def test_only_the_gateway_creates_models():
    offenders = {}
    for folder in ("app", "scripts"):
        for path in sorted((API / folder).rglob("*.py")):
            relative = path.relative_to(API)
            if relative in ALLOWED or relative.parts[:2] == ("app", "providers"):
                continue
            if names := model_imports(path):
                offenders[str(relative)] = sorted(names)
    assert offenders == {}
