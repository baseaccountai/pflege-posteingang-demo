"""Medication comparison (F03-AC7): record vs. new document, computed - never by the LLM.

Every medication of the new document is new, changed (strength or dosage differ) or
unchanged; every active medication of the record that the document no longer lists is
discontinued. Names, strengths and doses are compared after normalising spelling
("5mg" = "5 MG" = "5,0 mg"), so a different way of writing is not a change.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Literal

SLOTS = ("morgens", "mittags", "abends", "nachts")


@dataclass(frozen=True)
class Med:
    name: str
    strength: str | None = None
    dosage: dict[str, str] = field(default_factory=dict)
    hint: str | None = None
    id: str | None = None  # set for medications from the record


@dataclass(frozen=True)
class MedChange:
    kind: Literal["new", "changed", "unchanged", "discontinued"]
    name: str
    before: Med | None  # in the record
    after: Med | None  # in the document

    @property
    def medication_id(self) -> str | None:
        return self.before.id if self.before else None


def _number(text: str) -> str:
    """Numbers in canonical form: "5,0" -> "5", "0,50" -> "0.5", also inside "5.0mg"."""

    def canonical(match: re.Match) -> str:
        whole, _, fraction = match.group(0).partition(".")
        fraction = fraction.rstrip("0")
        return f"{whole}.{fraction}" if fraction else whole

    return re.sub(r"\d+(?:\.\d+)?", canonical, text.replace(",", "."))


def norm_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def norm_strength(strength: str | None) -> str:
    return _number("".join((strength or "").split()).casefold())


def norm_dosage(dosage: dict[str, str]) -> tuple[str, ...]:
    values = []
    for slot in SLOTS:
        value = _number((dosage.get(slot) or "").strip())
        values.append("0" if value in ("", "0") else value)
    return tuple(values)


def _same(a: Med, b: Med) -> bool:
    return norm_strength(a.strength) == norm_strength(b.strength) and norm_dosage(
        a.dosage
    ) == norm_dosage(b.dosage)


def diff(current: list[Med], proposed: list[Med]) -> list[MedChange]:
    """Changes in document order, then the discontinued ones in record order."""
    record = {norm_name(med.name): med for med in current}
    changes: list[MedChange] = []
    seen: set[str] = set()
    for med in proposed:
        key = norm_name(med.name)
        if key in seen:
            continue  # listed twice in the document: the first entry counts
        seen.add(key)
        before = record.get(key)
        if before is None:
            kind = "new"
        else:
            kind = "unchanged" if _same(before, med) else "changed"
        changes.append(MedChange(kind, med.name.strip(), before, med))
    for key, med in record.items():
        if key not in seen:
            changes.append(MedChange("discontinued", med.name.strip(), med, None))
    return changes


def diff_hash(changes: list[MedChange]) -> str:
    """Fingerprint of a comparison result (F03-AC8a): equal results, equal hash."""

    def side(med: Med | None):
        return None if med is None else [norm_strength(med.strength), norm_dosage(med.dosage)]

    canonical = [
        [change.kind, norm_name(change.name), side(change.before), side(change.after)]
        for change in changes
    ]
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()
