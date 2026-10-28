"""The production image (Docker, Vercel) installs only the runtime dependencies. Every
third-party module imported by app/ must therefore come from them - a dev-only package
(e.g. Pillow, once used only by samples/) would crash the API at startup there."""

import ast
import re
import sys
import tomllib
from importlib.metadata import distribution, packages_distributions
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).parents[1]


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def runtime_closure() -> set[str]:
    """The declared runtime dependencies and everything they require on this Python
    (with the extras we install, e.g. psycopg[binary,pool])."""
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    todo = [Requirement(text) for text in declared]
    seen: set[str] = set()
    while todo:
        requirement = todo.pop()
        name = normalise(requirement.name)
        if name in seen:
            continue
        seen.add(name)
        extras = requirement.extras or {""}
        for text in distribution(name).requires or []:
            needed = Requirement(text)
            if needed.marker is None or any(needed.marker.evaluate({"extra": e}) for e in extras):
                todo.append(needed)
    return seen


def imported_top_level_modules() -> set[str]:
    modules = set()
    for path in (ROOT / "app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                modules |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
    return {m for m in modules if m != "app" and m not in sys.stdlib_module_names}


def test_everything_app_imports_is_a_runtime_dependency():
    providers = packages_distributions()
    closure = runtime_closure()
    missing = {
        module: providers.get(module)
        for module in imported_top_level_modules()
        if not any(normalise(dist) in closure for dist in providers.get(module, []))
    }
    assert missing == {}, f"only installed as dev dependency (or not at all): {missing}"
