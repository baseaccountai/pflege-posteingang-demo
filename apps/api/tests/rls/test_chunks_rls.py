"""F05-AC1, AC4, AC5: chunks are derived data of approved documents, isolated per ward by
RLS; the search (app.match_chunks, security invoker) sees only the caller's wards, only one
embedding model, optionally only one resident, at most 6 hits."""

import uuid

import psycopg
import pytest

from app.auth.principal import Principal
from app.providers.embeddings.base import DIMENSION
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT, WB2_RESIDENT

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
NURSE_WB2 = Principal(
    sub="u-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2"
)
MODEL = "mistral-embed"
OTHER_RESIDENT_WB1 = "77777777-7777-7777-7777-777777777777"


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def unit(position: int, second: int | None = None) -> str:
    """A normalised vector as pgvector text: one (or two equal) non-zero positions."""
    values = [0.0] * DIMENSION
    values[position] = 1.0
    if second is not None:
        values[position] = values[second] = 2**-0.5
    return "[" + ",".join(str(v) for v in values) + "]"


def approved_document(
    ward: str, resident: str, status: str = "approved", doc_type: str = "arztbrief"
) -> str:
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, resident_id, uploaded_by, upload_session,"
        " status, doc_type, document_date) values (%s, %s, %s, 'u', 's', %s, %s, '2026-10-20')",
        [doc, ward, resident, status, doc_type],
    )
    return doc


def add_chunk(doc: str, ward: str, resident: str, vec: str, model: str = MODEL, text="x") -> str:
    return admin(
        "insert into public.chunks (document_id, ward_id, resident_id, doc_type, document_date,"
        " page, heading, content, embedding, embedding_model) values (%s, %s, %s, 'arztbrief',"
        " '2026-10-20', 1, 'Diagnosen', %s, %s::extensions.vector, %s) returning id::text",
        [doc, ward, resident, text, vec, model],
    )[0][0]


@pytest.fixture
def chunks(seeded) -> dict:
    admin(
        "insert into public.residents (id, ward_id, display_name) values (%s, 'wb1', 'Fr. Zweite')",
        [OTHER_RESIDENT_WB1],
    )
    wb1 = approved_document("wb1", WB1_RESIDENT)
    wb1_other = approved_document("wb1", OTHER_RESIDENT_WB1)
    wb2 = approved_document("wb2", WB2_RESIDENT)
    return {
        "wb1": add_chunk(wb1, "wb1", WB1_RESIDENT, unit(0), text="WB1 Muster-Bauer"),
        "wb1_other": add_chunk(wb1_other, "wb1", OTHER_RESIDENT_WB1, unit(0), text="WB1 Zweite"),
        "wb1_model": add_chunk(wb1, "wb1", WB1_RESIDENT, unit(0), model="other-model"),
        "wb2": add_chunk(wb2, "wb2", WB2_RESIDENT, unit(0), text="WB2 Testfeld"),
        "docs": {"wb1": wb1, "wb2": wb2},
    }


async def match(db, principal, vec: str, resident=None, limit=6, min_sim=0.0) -> list[tuple]:
    async with db.as_principal(principal) as conn:
        cur = await conn.execute(
            "select content, similarity"
            " from app.match_chunks(%s::extensions.vector, %s, %s, %s, %s)",
            [vec, MODEL, resident, limit, min_sim],
        )
        return await cur.fetchall()


async def test_the_search_finds_only_chunks_of_the_own_ward_and_model(db, chunks):
    wb1 = sorted(row[0] for row in await match(db, NURSE_WB1, unit(0)))
    wb2 = sorted(row[0] for row in await match(db, NURSE_WB2, unit(0)))
    assert wb1 == ["WB1 Muster-Bauer", "WB1 Zweite"]  # not WB2, not the other model
    assert wb2 == ["WB2 Testfeld"]


async def test_a_resident_filter_limits_the_search(db, chunks):
    rows = await match(db, NURSE_WB1, unit(0), resident=WB1_RESIDENT)
    assert [row[0] for row in rows] == ["WB1 Muster-Bauer"]
    # A WB2 resident as filter from WB1 gives nothing (RLS), not an error.
    assert await match(db, NURSE_WB1, unit(0), resident=WB2_RESIDENT) == []


async def test_hits_are_ordered_by_similarity_and_cut_by_threshold_and_limit(db, chunks):
    doc = chunks["docs"]["wb1"]
    add_chunk(doc, "wb1", WB1_RESIDENT, unit(1), text="orthogonal")
    add_chunk(doc, "wb1", WB1_RESIDENT, unit(0, 1), text="halb")
    rows = await match(db, NURSE_WB1, unit(0), resident=WB1_RESIDENT, min_sim=0.5)
    assert [row[0] for row in rows] == ["WB1 Muster-Bauer", "halb"]
    assert rows[0][1] == pytest.approx(1.0) and rows[1][1] == pytest.approx(2**-0.5)
    for i in range(10):
        add_chunk(doc, "wb1", WB1_RESIDENT, unit(0), text=f"viele {i}")
    assert len(await match(db, NURSE_WB1, unit(0), limit=50)) == 6  # never more than 6 (AC4)


async def test_wb2_cannot_delete_wb1_chunks_but_wb1_can_replace_its_own(db, chunks):
    async with db.as_principal(NURSE_WB2) as conn:
        cur = await conn.execute("delete from public.chunks where id = %s", [chunks["wb1"]])
        assert cur.rowcount == 0
    async with db.as_principal(NURSE_WB1) as conn:
        cur = await conn.execute("delete from public.chunks where id = %s", [chunks["wb1"]])
        assert cur.rowcount == 1


async def insert_as(db, principal, doc: str, ward: str, resident: str) -> None:
    async with db.as_principal(principal) as conn:
        await conn.execute(
            "insert into public.chunks (document_id, ward_id, resident_id, doc_type,"
            " document_date, page, heading, content, embedding, embedding_model)"
            " values (%s, %s, %s, 'arztbrief', '2026-10-20', 1, null, 'neu',"
            " %s::extensions.vector, %s)",
            [doc, ward, resident, unit(2), MODEL],
        )


async def test_a_nurse_indexes_approved_documents_of_her_ward(db, chunks):
    await insert_as(db, NURSE_WB1, chunks["docs"]["wb1"], "wb1", WB1_RESIDENT)
    assert admin("select count(*) from public.chunks where content = 'neu'") == [(1,)]


@pytest.mark.parametrize(
    "case",
    ["foreign-ward", "wrong-resident", "not-approved", "wb2-row-for-wb1-document", "wrong-type"],
)
async def test_chunks_that_do_not_belong_to_the_document_are_refused(db, chunks, case):
    doc = chunks["docs"]["wb1"]
    principal, ward, resident = NURSE_WB1, "wb1", WB1_RESIDENT
    if case == "foreign-ward":
        principal = NURSE_WB2
    elif case == "wrong-resident":
        resident = OTHER_RESIDENT_WB1  # same ward, but not the document's resident
    elif case == "wrong-type":  # the chunk says arztbrief, the document is a plan
        doc = approved_document("wb1", WB1_RESIDENT, doc_type="medikationsplan")
    elif case == "not-approved":
        doc = approved_document("wb1", WB1_RESIDENT, status="ready_for_review")
    else:
        principal, ward, resident = NURSE_WB2, "wb2", WB2_RESIDENT
    with pytest.raises(psycopg.Error):
        await insert_as(db, principal, doc, ward, resident)


async def test_chunks_cannot_be_changed_afterwards(db, chunks):
    async with db.as_principal(NURSE_WB1) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            await conn.execute("update public.chunks set content = 'anders'")


def test_anon_has_no_access():
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        assert conn.execute(
            "select has_table_privilege('anon', 'public.chunks', 'select'),"
            " has_function_privilege('anon', 'app.match_chunks(extensions.vector, text, uuid,"
            " int, float)', 'execute')"
        ).fetchone() == (False, False)


def test_chunks_go_with_their_document():
    # The nightly reset truncates documents with CASCADE; chunks must hang on them.
    rows = admin(
        "select confrelid::regclass::text from pg_constraint"
        " where conrelid = 'public.chunks'::regclass and contype = 'f'"
    )
    assert ("documents",) in rows or ("public.documents",) in rows
