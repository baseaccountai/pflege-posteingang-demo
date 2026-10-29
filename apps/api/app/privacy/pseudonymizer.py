"""Pseudonymisation before a model sees a text (F06-AC2, AC3, AC6, AC10).

What gets replaced, in this order:

1. Residents (all of the home, also other wards): "Hr. Muster-Bauer", "Herrn Muster-Bauer",
   "Muster-Bauer" -> "Bewohner_A17". The code is stored per resident (residents.pseudonym)
   and stays the same everywhere, so stored chunks and a later question use the same code.
   The bare surname counts only when written with a capital letter: "Probe" is Hr. Probe,
   "eine probe Aufnahme" is not. Some surnames are ordinary words ("Vorlage"); replacing
   such a word by mistake costs a little meaning, missing a name would cost privacy.
2. Their birth dates in the usual spellings -> "Geburtsdatum_A17". Other dates stay: the
   date of a letter or of a check-up is needed to answer questions.
3. Other people after a title or a form of address ("Dr. med. Lorem", "Frau Lindner")
   -> "Person_1", "Person_2", ... numbered per call.
4. Phone numbers, e-mail addresses, health insurance numbers, street + house number
   -> "[TELEFON_1]", "[E-MAIL_1]", "[VERSICHERTENNR_1]", "[ADRESSE_1]".

One call (a question with its sources, a document) shares one mapping, so the same person
keeps the same placeholder. The mapping placeholder -> original only lives in memory; it
is never sent to a model (F06-AC8).
"""

import re
from dataclasses import dataclass, field
from datetime import date

MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]  # fmt: skip

TITLE = r"(?:Hr\.|Herrn?|Fr\.|Frau)"
NAME = r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)*"
NO_WORD_BEFORE = r"(?<![\w-])"
NO_WORD_AFTER = r"(?![\w-])"

# Kinds of other data, each with its placeholder name.
# A form of address and/or academic titles ("Frau Dr. med.", "Prof. Dr.", "Herrn"), then the name.
ACADEMIC = r"(?:(?:Prof\.|Dr\.|med\.)\s*)"
ADDRESS_OR_TITLE = rf"(?:(?:Herrn?|Frau|Hr\.|Fr\.)\s*{ACADEMIC}*|(?:Prof\.|Dr\.)\s*{ACADEMIC}*)"
# First name(s) and surname: up to three words on the same line ("Frau Anna Meier"). German
# nouns are capitalised too, so a following noun may be swallowed - privacy before wording.
OTHER_PERSON = re.compile(ADDRESS_OR_TITLE + NAME + r"(?:[ \t]+" + NAME + r"){0,2}" + NO_WORD_AFTER)
CONTACT = [
    # Each pattern may only start at the beginning of a word: otherwise a long word without
    # spaces would be scanned again from every position (slow, could stall the API).
    ("E-MAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("VERSICHERTENNR", re.compile(r"\b[A-Z]\d{9}\b")),
    (
        "ADRESSE",
        re.compile(
            r"(?<![\w-])[A-ZÄÖÜ][\wäöüß-]*(?:straße|strasse|str\.|weg|platz|allee|gasse|ring)"
            r"\s+\d+\s?[a-z]?\b"
        ),
    ),
    ("TELEFON", re.compile(r"(?<![\w+])(?:\+49[\s()/-]*|0)\d[\d\s()/-]{4,}\d")),
]
PLACEHOLDER = re.compile(
    r"Bewohner_([A-Z]\d{2})|Geburtsdatum_([A-Z]\d{2})|Person_\d+"
    r"|\[(?:TELEFON|E-MAIL|VERSICHERTENNR|ADRESSE)_\d+\]"
)


@dataclass(frozen=True)
class KnownResident:
    resident_id: str
    pseudonym: str  # e.g. "A17"
    display_name: str  # e.g. "Hr. Muster-Bauer"
    birth_date: date | None


@dataclass
class Pseudonymized:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)  # placeholder -> original


def birth_date_forms(day: date) -> list[str]:
    """03.04.1941, 3.4.1941, 03.04.41, 3.4.41, 1941-04-03, 3. April 1941, 03. April 1941."""
    d, m, y = day.day, day.month, day.year
    return [
        f"{d:02}.{m:02}.{y}",
        f"{d}.{m}.{y}",
        f"{d:02}.{m:02}.{y % 100:02}",
        f"{d}.{m}.{y % 100:02}",
        day.isoformat(),
        f"{d}. {MONTHS[m - 1]} {y}",
        f"{d:02}. {MONTHS[m - 1]} {y}",
    ]


def _surname(display_name: str) -> str:
    return re.sub(rf"^{TITLE}\s*", "", display_name).strip()


class Pseudonymizer:
    def __init__(self, residents: list[KnownResident]):
        self.residents = {r.pseudonym: r for r in residents}
        # Longest surnames first, so "Muster-Bauer" wins over a shorter name inside it.
        ordered = sorted(residents, key=lambda r: len(_surname(r.display_name)), reverse=True)
        self._names: list[tuple[re.Pattern, re.Pattern, str]] = []
        self._birth_dates: list[tuple[re.Pattern, str]] = []
        for r in ordered:
            name = re.escape(_surname(r.display_name))
            titled = re.compile(rf"{TITLE}\s*{name}{NO_WORD_AFTER}", re.IGNORECASE)
            bare = re.compile(rf"{NO_WORD_BEFORE}{name}{NO_WORD_AFTER}")  # capital letter only
            self._names.append((titled, bare, r.pseudonym))
            if r.birth_date:
                forms = sorted(birth_date_forms(r.birth_date), key=len, reverse=True)
                pattern = r"(?<![\d.])(?:" + "|".join(map(re.escape, forms)) + r")(?![\d])"
                self._birth_dates.append((re.compile(pattern), r.pseudonym))

    def pseudonymize(self, text: str, mapping: dict[str, str] | None = None) -> Pseudonymized:
        """Replaces in `text`; new placeholders are added to `mapping` (shared per call)."""
        mapping = mapping if mapping is not None else {}
        for titled, bare, code in self._names:
            text = bare.sub(f"Bewohner_{code}", titled.sub(f"Bewohner_{code}", text))
        for pattern, code in self._birth_dates:
            text = pattern.sub(f"Geburtsdatum_{code}", text)
        text = OTHER_PERSON.sub(lambda m: _numbered(mapping, "Person_{}", m.group(0)), text)
        for kind, pattern in CONTACT:
            template = f"[{kind}_{{}}]"
            text = pattern.sub(lambda m, t=template: _numbered(mapping, t, m.group(0)), text)
        return Pseudonymized(text, mapping)

    def restore(self, text: str, mapping: dict[str, str], visible: set[str]) -> str:
        """Placeholders back to the original. Residents only if the caller may see them
        (`visible` = resident ids from RLS); unknown placeholders stay as they are."""

        def original(match: re.Match) -> str:
            code = match.group(1) or match.group(2)
            if code:
                resident = self.residents.get(code)
                if resident is None or resident.resident_id not in visible:
                    return match.group(0)
                if match.group(1):
                    return resident.display_name
                if resident.birth_date is None:
                    return match.group(0)
                return resident.birth_date.strftime("%d.%m.%Y")
            return mapping.get(match.group(0), match.group(0))

        return PLACEHOLDER.sub(original, text)

    def leaks(self, text: str) -> bool:
        """True if a resident's name or birth date is still in the text (F06-AC10)."""
        return any(t.search(text) or b.search(text) for t, b, _ in self._names) or any(
            pattern.search(text) for pattern, _ in self._birth_dates
        )


def _numbered(mapping: dict[str, str], template: str, original: str) -> str:
    """The placeholder this original already has in the mapping, or the next free number."""
    for placeholder, value in mapping.items():
        if value == original and placeholder.startswith(template.split("{}")[0]):
            return placeholder
    prefix = template.split("{}")[0]
    number = 1 + sum(1 for placeholder in mapping if placeholder.startswith(prefix))
    placeholder = template.format(number)
    mapping[placeholder] = original
    return placeholder
