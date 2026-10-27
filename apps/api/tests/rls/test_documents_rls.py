"""F02-AC5, F02-AC12, F02-AC13: documents and their files stay in their ward (RLS)."""

import uuid

import psycopg
import pytest

from app.auth.principal import Principal
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT, WB2_RESIDENT

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
NURSE_WB2 = Principal(
    sub="u-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2"
)
PDL = Principal(sub="u-pdl", app_role="pdl", ward_ids=("wb1", "wb2"), display_name="PDL")
WB1_DOC = "aaaaaaaa-0000-0000-0000-000000000001"
WB2_DOC = "aaaaaaaa-0000-0000-0000-000000000002"
INSERT_FILE = (
    "insert into public.document_files (document_id, ward_id, mime, size_bytes, content)"
    " values (%s, %s, %s, %s, %s)"
)
# As a principal: uploaded_by comes from the claims (default app.uid()).
INSERT_DOC = "insert into public.documents (id, ward_id, upload_session) values (%s, %s, 'sid')"


@pytest.fixture
def documents(seeded):
    """One document with a file per ward, inserted with admin rights."""
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        for doc_id, ward in [(WB1_DOC, "wb1"), (WB2_DOC, "wb2")]:
            conn.execute(
                "insert into public.documents (id, ward_id, uploaded_by, upload_session)"
                " values (%s, %s, 'u-admin', 'sid')",
                [doc_id, ward],
            )
            conn.execute(INSERT_FILE, [doc_id, ward, "application/pdf", 4, b"%PDF"])


async def rows(db, principal, sql: str) -> list[tuple]:
    async with db.as_principal(principal) as conn:
        return await (await conn.execute(sql)).fetchall()


async def test_wb2_sees_no_wb1_document_or_file_without_filter(db, documents):
    assert await rows(db, NURSE_WB2, "select id::text from public.documents") == [(WB2_DOC,)]
    files = await rows(db, NURSE_WB2, "select document_id::text from public.document_files")
    assert files == [(WB2_DOC,)]


async def test_nurse_creates_a_document_with_file_in_own_ward(db, documents):
    doc_id = str(uuid.uuid4())
    async with db.as_principal(NURSE_WB1) as conn:
        await conn.execute(INSERT_DOC, [doc_id, "wb1"])
        await conn.execute(INSERT_FILE, [doc_id, "wb1", "image/png", 1, b"x"])
        cur = await conn.execute(
            "select status::text, attempts, uploaded_by from public.documents where id = %s",
            [doc_id],
        )
        assert await cur.fetchone() == ("uploaded", 0, "u-wb1")


async def test_uploader_cannot_be_forged(db, documents):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(NURSE_WB1) as conn:
            await conn.execute(
                "insert into public.documents (ward_id, uploaded_by, upload_session)"
                " values ('wb1', 'someone-else', 'sid')"
            )


async def test_wb2_cannot_create_a_document_in_wb1(db, documents):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(INSERT_DOC, [str(uuid.uuid4()), "wb1"])


async def test_wb2_cannot_attach_a_file_to_a_wb1_document(db, documents):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(INSERT_FILE, [WB1_DOC, "wb1", "image/png", 1, b"x"])


async def test_a_file_cannot_claim_another_ward_than_its_document(db, documents):
    # A WB1 document without a file yet; a "wb2" file row for it is rejected by the
    # composite key (document + ward), even though RLS would allow a wb2 row.
    bare = str(uuid.uuid4())
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        conn.execute(
            "insert into public.documents (id, ward_id, uploaded_by, upload_session)"
            " values (%s, 'wb1', 'u-admin', 'sid')",
            [bare],
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(INSERT_FILE, [bare, "wb2", "image/png", 1, b"x"])


async def test_ward_id_cannot_be_changed(db, documents):
    with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.InsufficientPrivilege)):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(
                "update public.documents set ward_id = 'wb1' where id = %s", [WB2_DOC]
            )


async def test_even_pdl_cannot_move_a_document_between_wards(db, documents):
    # RLS allows both wards for the PDL, so only the trigger stops the move.
    async with db.as_principal(PDL) as conn:
        doc_id = str(uuid.uuid4())
        await conn.execute(INSERT_DOC, [doc_id, "wb1"])
    with pytest.raises(psycopg.errors.CheckViolation):
        async with db.as_principal(PDL) as conn:
            await conn.execute(
                "update public.documents set ward_id = 'wb2' where id = %s", [doc_id]
            )


async def test_wb2_document_cannot_reference_a_wb1_resident(db, documents):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(
                "update public.documents set resident_id = %s where id = %s",
                [WB1_RESIDENT, WB2_DOC],
            )


async def test_resident_is_set_once_and_then_fixed(db, documents):
    async with db.as_principal(NURSE_WB2) as conn:
        await conn.execute(
            "update public.documents set resident_id = %s where id = %s", [WB2_RESIDENT, WB2_DOC]
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(
                "update public.documents set resident_id = null where id = %s", [WB2_DOC]
            )


async def test_status_starts_as_uploaded_and_only_known_values_are_allowed(db, documents):
    with pytest.raises(psycopg.errors.InvalidTextRepresentation):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(
                "update public.documents set status = 'hacked' where id = %s", [WB2_DOC]
            )


@pytest.mark.parametrize(
    "sql",
    [
        "delete from public.documents",
        "delete from public.document_files",
        "update public.document_files set content = 'x'",
    ],
)
async def test_documents_and_files_cannot_be_deleted_and_files_not_changed(db, documents, sql):
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(NURSE_WB2) as conn:
            await conn.execute(sql)


async def test_file_size_is_capped_at_4_mb(db, documents):
    with pytest.raises(psycopg.errors.CheckViolation):
        async with db.as_principal(NURSE_WB2) as conn:
            doc_id = str(uuid.uuid4())
            await conn.execute(INSERT_DOC, [doc_id, "wb2"])
            size = 4 * 1024 * 1024 + 1
            await conn.execute(INSERT_FILE, [doc_id, "wb2", "application/pdf", size, b"x" * size])
