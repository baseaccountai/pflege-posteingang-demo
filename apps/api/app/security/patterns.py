"""Layer 1b of the prompt-injection protection: rules for suspicious text (F07-AC3).

The rules live as data in app/security/patterns/*.toml (id, category, language, regular
expression, explanation), separate from the test corpus that measures them (F07-AC13,
F13). A section matches if any rule finds something in it; the explanation is shown to the
nurse on the screen "Angriff erkannt".
"""

import re
import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PATTERN_DIR = Path(__file__).parent / "patterns"


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    lang: str
    explanation: str
    regex: re.Pattern


@cache
def load_rules() -> tuple[Rule, ...]:
    rules = []
    for path in sorted(PATTERN_DIR.glob("*.toml")):
        for item in tomllib.loads(path.read_text(encoding="utf-8"))["rule"]:
            rules.append(
                Rule(
                    id=item["id"],
                    category=item["category"],
                    lang=item["lang"],
                    explanation=item["explanation"],
                    regex=re.compile(item["pattern"], re.IGNORECASE),
                )
            )
    return tuple(rules)


def matching_rules(text: str, rules: tuple[Rule, ...] | None = None) -> list[Rule]:
    # OCR breaks sentences at every printed line: rules see the text as one line.
    flat = re.sub(r"\s+", " ", text)
    return [rule for rule in rules or load_rules() if rule.regex.search(flat)]
