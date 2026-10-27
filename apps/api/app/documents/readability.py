"""Readability check after OCR (F02-AC7): is there enough text, and is it a care document?

Deliberately simple and explainable: fewer than 80 visible characters means the photo was
empty, blurred or cut off; fewer than two different care words means it is probably not a
care document (recipe, invoice). Such documents get no field suggestion - an LLM would
otherwise invent fields from noise.
"""

import re
from dataclasses import dataclass

MIN_CHARACTERS = 80
MIN_CARE_WORDS = 2

# Word stems, matched case-insensitively anywhere in a word ("Hausarzt", "Patientin").
CARE_STEMS = (
    "diagnose", "medikation", "medikament", "arzt", "ärzt", "bewohner", "patient",
    "entlassung", "pflege", "dosierung", "befund", "therapie", "klinik", "anamnese",
    "wiedervorlage", "überleitung", "tablette",
)  # fmt: skip
# Units are short, so they must stand alone ("mg", not "Zimmgang").
CARE_UNITS = re.compile(r"\b(mg|µg|ml|i\.e\.)(?=\W|$)", re.IGNORECASE)


@dataclass(frozen=True)
class Readability:
    readable: bool
    error_code: str | None = None  # unreadable_text | not_care_document


def care_words_found(text: str) -> set[str]:
    lower = text.lower()
    found = {stem for stem in CARE_STEMS if stem in lower}
    found |= {match.lower() for match in CARE_UNITS.findall(text)}
    return found


def check_readability(text: str) -> Readability:
    visible = re.sub(r"\s+", "", text)
    if len(visible) < MIN_CHARACTERS:
        return Readability(False, "unreadable_text")
    if len(care_words_found(text)) < MIN_CARE_WORDS:
        return Readability(False, "not_care_document")
    return Readability(True)
