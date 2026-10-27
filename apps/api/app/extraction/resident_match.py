"""Resident suggestion for a document (F03-AC5, F03-AC6).

Compares the name in the document with the residents the caller may see - RLS decides
which those are, so a resident of another ward is never suggested. Exactly one fitting
resident gives a suggestion; none or several give none ("Bewohner bitte auswählen").
The nurse always confirms the resident herself before anything is approved.
"""

import re
from dataclasses import dataclass

from psycopg import AsyncConnection

TITLES = {"hr", "herr", "fr", "frau", "dr", "med", "prof"}
UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


@dataclass(frozen=True)
class Candidate:
    id: str
    display_name: str


def parse_name(name: str | None) -> tuple[str | None, str] | None:
    """(first name or initial, surname), lower case, umlauts spelled out, titles removed."""
    text = (name or "").casefold().translate(UMLAUTS)
    if "," in text:  # "Testfeld, Anna"
        surname_part, first_part = text.split(",", 1)
        text = f"{first_part} {surname_part}"
    words = [w.strip(".") for w in re.split(r"\s+", text) if w.strip(".")]
    words = [w for w in words if w not in TITLES]
    if not words:
        return None
    return (words[0] if len(words) > 1 else None), words[-1]


def _first_names_fit(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return True  # one side has no first name: the surname decides
    if len(a) == 1 or len(b) == 1:
        return a[0] == b[0]  # initial "A." against "Anna"
    return a == b


def match_resident(name: str | None, residents: list[Candidate]) -> str | None:
    wanted = parse_name(name)
    if wanted is None:
        return None
    first, surname = wanted
    hits = []
    for resident in residents:
        known = parse_name(resident.display_name)
        if known and known[1] == surname and _first_names_fit(first, known[0]):
            hits.append(resident.id)
    return hits[0] if len(hits) == 1 else None


async def suggest_resident(conn: AsyncConnection, name: str | None) -> str | None:
    """Within a transaction as the caller: only residents visible under RLS count."""
    cur = await conn.execute("select id::text, display_name from public.residents")
    residents = [Candidate(id, display_name) for id, display_name in await cur.fetchall()]
    return match_resident(name, residents)
