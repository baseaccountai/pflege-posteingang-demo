"""F05-AC4 to AC7: the search sees only the own wards, a resident filter (chosen or named in
the question) narrows it, and a foreign or unknown resident gives exactly the same "no hits"
as nothing found - without calling a model."""

import uuid

import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.auth.principal import Principal
from app.providers.embeddings.fake import FakeEmbeddings
from app.rag.indexer import Indexer
from app.rag.retrieval import NO_HITS, retrieve
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT, WB2_RESIDENT

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
NURSE_WB2 = Principal(
    sub="u-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2"
)
SECOND_WB1 = "77777777-7777-7777-7777-777777777777"


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


@pytest.fixture
async def indexed(db, seeded):
    """Three residents with one indexed letter each: two in WB1, one in WB2."""
    admin("truncate public.usage_counters")
    admin(
        "insert into public.residents (id, ward_id, display_name) values (%s, 'wb1', 'Fr. Zweite')",
        [SECOND_WB1],
    )
    texts = {
        WB1_RESIDENT: (
            "wb1",
            NURSE_WB1,
            "## Medikation\nRamipril 5 mg morgens gegen Bluthochdruck",
        ),
        SECOND_WB1: ("wb1", NURSE_WB1, "## Medikation\nRamipril 10 mg abends nach Herzinfarkt"),
        WB2_RESIDENT: ("wb2", NURSE_WB2, "## Medikation\nRamipril 2,5 mg morgens bei Diabetes"),
    }
    for resident, (ward, nurse, text) in texts.items():
        doc = str(uuid.uuid4())
        admin(
            "insert into public.documents (id, ward_id, resident_id, uploaded_by, upload_session,"
            " status, doc_type, document_date, ocr_pages, indexing_status) values (%s, %s, %s,"
            " 'u', 's', 'approved', 'arztbrief', '2026-10-20', %s, 'pending')",
            [doc, ward, resident, Jsonb([{"page": 1, "markdown": text}])],
        )
        await Indexer(db, FakeEmbeddings()).run(nurse, doc)
    yield
    admin("truncate public.usage_counters")


async def ask(db, question, principal=NURSE_WB1, resident_id=None, embeddings=None):
    embeddings = embeddings or FakeEmbeddings()
    return await retrieve(
        db, principal, embeddings, question, resident_id, min_similarity=0.1
    ), embeddings


async def test_a_question_searches_only_the_own_ward(db, indexed):
    result, _ = await ask(db, "Wie ist Ramipril dosiert?")
    assert {hit.resident_name for hit in result.hits} == {"Hr. Muster-Bauer", "Fr. Zweite"}
    result, _ = await ask(db, "Wie ist Ramipril dosiert?", principal=NURSE_WB2)
    assert {hit.resident_name for hit in result.hits} == {"Fr. Testfeld"}


async def test_a_resident_named_in_the_question_becomes_the_filter(db, indexed):
    result, _ = await ask(db, "Wie ist Ramipril bei Hr. Muster-Bauer dosiert?")
    assert [hit.resident_name for hit in result.hits] == ["Hr. Muster-Bauer"]
    assert "5 mg" in result.hits[0].content
    assert (result.hits[0].doc_type, result.hits[0].page) == ("arztbrief", 1)


async def test_a_chosen_resident_filters_the_search(db, indexed):
    result, _ = await ask(db, "Wie ist Ramipril dosiert?", resident_id=SECOND_WB1)
    assert [hit.resident_name for hit in result.hits] == ["Fr. Zweite"]


@pytest.mark.parametrize(
    ("question", "resident_id"),
    [
        ("Wie ist Ramipril bei Fr. Testfeld dosiert?", None),  # exists, but in WB2
        ("Wie ist Ramipril bei Hr. Niemand dosiert?", None),  # does not exist
        ("Wie ist Ramipril dosiert?", WB2_RESIDENT),  # chosen, but foreign
        ("Wie ist Ramipril dosiert?", str(uuid.uuid4())),  # chosen, unknown
        ("Wie ist Ramipril dosiert?", "kein-uuid"),  # malformed
    ],
    ids=["foreign-name", "unknown-name", "foreign-filter", "unknown-filter", "malformed-filter"],
)
async def test_foreign_and_unknown_residents_look_exactly_like_no_hits(
    db, indexed, question, resident_id
):
    result, embeddings = await ask(db, question, resident_id=resident_id)
    assert result == NO_HITS
    assert embeddings.calls == []  # not even the question is embedded


async def test_nothing_similar_enough_is_no_hits(db, indexed):
    result, embeddings = await ask(db, "Wann ist der nächste Friseurtermin?")
    assert result == NO_HITS
    assert embeddings.calls == [["Wann ist der nächste Friseurtermin?"]]


async def test_the_question_counts_against_the_embedding_quota(db, indexed):
    before = admin("select count from public.usage_counters where kind = 'embed_chunk'")[0][0]
    await ask(db, "Wie ist Ramipril dosiert?")
    assert admin("select count from public.usage_counters where kind = 'embed_chunk'") == [
        (before + 1,)
    ]
