"""Measuring the prompt-injection protection against a test corpus (F13).

The corpus lives in tests/security/corpus/*.jsonl, apart from the rules it measures
(F07-AC13): one JSON object per line with id, text, lang, category, source and license.

Key figures (F13-AC2a): an entry counts as detected if at least one checked layer flags it.

    detection rate    = detected attacks         / all attacks
    false alarm rate  = detected harmless texts  / all harmless texts

both overall and per category (every entry has exactly one). Which layers count is decided
by the caller's `flags` function: rules alone, checker alone, or both.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

CORPUS_DIR = Path(__file__).parents[2] / "tests" / "security" / "corpus"
# Questions and agent tasks (F13-AC9): measured apart, with the request instruction.
REQUESTS_DIR = Path(__file__).parents[2] / "tests" / "security" / "requests"
ATTACK_CATEGORIES = frozenset(
    {
        "role_override",
        "ignore_instructions",
        "exfiltration",
        "dose_manipulation",
        "tool_abuse",
        "hidden_instruction",
        "jailbreak",
    }
)


@dataclass(frozen=True)
class Entry:
    id: str
    text: str
    lang: str
    category: str
    source: str
    license: str
    file: str

    @property
    def is_attack(self) -> bool:
        return self.category != "benign"


@dataclass(frozen=True)
class Rate:
    hits: int
    total: int

    @property
    def percent(self) -> str:
        """German notation, one decimal: "66,7 %"; "–" if there is nothing to count."""
        if not self.total:
            return "–"
        return f"{100 * self.hits / self.total:.1f} %".replace(".", ",")


@dataclass(frozen=True)
class Result:
    detection: Rate
    false_alarms: Rate
    by_category: dict[str, Rate] = field(default_factory=dict)
    missed: list[str] = field(default_factory=list)  # ids of attacks nobody flagged
    false_alarm_ids: list[str] = field(default_factory=list)  # harmless, but flagged


def load_corpus(folder: Path = CORPUS_DIR) -> list[Entry]:
    entries = []
    for path in sorted(folder.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                entries.append(
                    Entry(
                        item["id"],
                        item["text"],
                        item["lang"],
                        item["category"],
                        item["source"],
                        item["license"],
                        path.name,
                    )
                )
    return entries


def evaluate(entries: list[Entry], flags: Callable[[Entry], bool]) -> Result:
    flagged = {entry.id for entry in entries if flags(entry)}
    attacks = [e for e in entries if e.is_attack]
    harmless = [e for e in entries if not e.is_attack]
    categories: dict[str, list[Entry]] = {}
    for entry in entries:
        categories.setdefault(entry.category, []).append(entry)
    return Result(
        detection=Rate(sum(e.id in flagged for e in attacks), len(attacks)),
        false_alarms=Rate(sum(e.id in flagged for e in harmless), len(harmless)),
        by_category={
            name: Rate(sum(e.id in flagged for e in group), len(group))
            for name, group in categories.items()
        },
        missed=[e.id for e in attacks if e.id not in flagged],
        false_alarm_ids=[e.id for e in harmless if e.id in flagged],
    )
