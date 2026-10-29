"""Finding the chunks for a question (F05-AC4 to AC7).

1. Which resident? A resident chosen in the app (link from the record) or named in the
   question ("Hr. Muster-Bauer") becomes the filter - but only if the caller can see him.
   Residents are looked up as the caller, so RLS decides who exists.
2. A resident that cannot be found - in another ward or not at all - ends here with
   NO_HITS: same answer, no model call, so the answer does not tell whether a person exists
   elsewhere (AC7).
3. Otherwise the question is embedded (one unit of the embedding quota) - pseudonymised,
   the name has done its job as a filter in step 1 (F06-AC5) - and compared with
   the chunks via app.match_chunks: own wards only (RLS), the configured model only, at most
   6 hits above the minimum similarity. Nothing similar enough is NO_HITS as well.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import date

from app.auth.principal import Principal
from app.db import Database
from app.privacy.gateway import ModelGateway
from app.quotas import consume

MAX_HITS = 6

# "Hr. Muster-Bauer", "Herrn Probe", "Frau Beispiel", "Fr.Vorlage": the word after the title.
TITLED_NAME = re.compile(
    r"\b(?:Hr\.|Fr\.|(?:Herrn?|Frau)(?!\w))\s*([A-ZÄÖÜ][\wäöüß]*(?:-[A-ZÄÖÜ][\wäöüß]*)*)"
)
TITLE = re.compile(r"^(?:Hr\.|Herrn?|Fr\.|Frau)\s*", re.IGNORECASE)


def titled_names(question: str) -> list[str]:
    """Names that follow a form of address, in lower case."""
    return [name.casefold() for name in TITLED_NAME.findall(question)]


def surname(display_name: str) -> str:
    """ "Hr. Muster-Bauer" -> "muster-bauer" (the residents' display names carry the title)."""
    return TITLE.sub("", display_name).strip().casefold()


@dataclass(frozen=True)
class Hit:
    chunk_id: str
    document_id: str
    resident_id: str
    resident_name: str
    doc_type: str | None
    document_date: date | None
    page: int
    heading: str | None
    content: str
    similarity: float


@dataclass(frozen=True)
class Retrieval:
    hits: list[Hit] = field(default_factory=list)


NO_HITS = Retrieval()


async def retrieve(
    db: Database,
    principal: Principal,
    gateway: ModelGateway,
    question: str,
    resident_id: str | None,
    min_similarity: float,
) -> Retrieval:
    async with db.as_principal(principal) as conn:
        cur = await conn.execute("select id::text, display_name from public.residents")
        visible = dict(await cur.fetchall())  # id -> name, only the own wards (RLS)

    resident = _resident_filter(question, resident_id, visible)
    if resident is False:
        return NO_HITS  # named or chosen, but not found: no model call (AC7)

    async with db.as_principal(principal) as conn:
        await consume(conn, "embed_chunk", 1)
    pseudonymizer = await gateway.pseudonymizer()
    (query,) = await gateway.embed([pseudonymizer.pseudonymize(question).text])

    async with db.as_principal(principal) as conn:
        cur = await conn.execute(
            "select id::text, document_id::text, resident_id::text, doc_type::text,"
            " document_date, page, heading, content, similarity"
            " from app.match_chunks(%s::extensions.vector, %s, %s, %s, %s)",
            [
                "[" + ",".join(map(str, query)) + "]",
                gateway.embedding_model,
                resident,
                MAX_HITS,
                min_similarity,
            ],
        )
        rows = await cur.fetchall()
    if not rows:
        return NO_HITS
    return Retrieval(
        hits=[
            Hit(chunk, doc, res, visible.get(res, ""), dtype, ddate, page, heading, text, sim)
            for chunk, doc, res, dtype, ddate, page, heading, text, sim in rows
        ]
    )


def _resident_filter(question: str, resident_id: str | None, visible: dict[str, str]):
    """The resident to search for: an id, None (whole own wards) or False (not found)."""
    if resident_id is not None:
        try:
            resident_id = str(uuid.UUID(resident_id))
        except ValueError:
            return False
        return resident_id if resident_id in visible else False

    by_surname: dict[str, list[str]] = {}
    for rid, name in visible.items():
        by_surname.setdefault(surname(name), []).append(rid)

    named = titled_names(question)
    if named:
        # A name with a title must be one of the own residents - otherwise no hits.
        found = {rid for name in named for rid in by_surname.get(name, [])}
        if len(found) != len(set(named)) or not found:
            return False
        return found.pop() if len(found) == 1 else None

    # Without a title only an exact, unique surname of the own wards counts.
    words = set(re.findall(r"[\wäöüß]+(?:-[\wäöüß]+)*", question.casefold()))
    matches = [rids[0] for name, rids in by_surname.items() if name in words and len(rids) == 1]
    return matches[0] if len(matches) == 1 else None
