"""F07-AC1, AC5: the database itself keeps the injection check in the path - no field
suggestion without a check result, every retry after the OCR checks again - and findings
stay in their ward, written once, never changed."""

import uuid

import psycopg
import pytest
from psycopg.types.json import Jsonb

from app.auth.principal import Principal
from tests.rls.conftest import ADMIN_DSN, WB1_RESIDENT

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
NURSE_WB2 = Principal(
    sub="u-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2"
)
PAGES = [{"page": 1, "markdown": "# Arztbrief\nRamipril 5 mg"}]


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def document(status: str, screened: bool = False) -> str:
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, uploaded_by, upload_session, status,"
        " ocr_pages, screened_pages, screening_result)"
        " values (%s, 'wb1', 'u-wb1', 's', %s, %s, %s, %s)",
        [
            doc,
            status,
            Jsonb(PAGES),
            Jsonb(PAGES) if screened else None,
            "clean" if screened else None,
        ],
    )
    return doc


async def move(db, doc: str, to: str, **columns) -> None:
    sets = ", ".join([f"{c} = %({c})s" for c in columns] + ["status = %(to)s"])
    params = {"to": to, "id": doc} | {
        c: Jsonb(v) if isinstance(v, list) else v for c, v in columns.items()
    }
    async with db.as_principal(NURSE_WB1) as conn:
        await conn.execute(f"update public.documents set {sets} where id = %(id)s", params)


@pytest.mark.parametrize("start", ["processing", "failed"])
async def test_extracting_is_reached_only_through_the_check(db, seeded, start):
    doc = document(start, screened=True)  # even with an old result: never skip the step
    with pytest.raises(psycopg.errors.CheckViolation):
        await move(db, doc, "extracting")


async def test_the_check_needs_a_result_and_cleaned_pages_before_extracting(db, seeded):
    doc = document("screening")
    with pytest.raises(psycopg.errors.CheckViolation):
        await move(db, doc, "extracting")
    await move(db, doc, "extracting", screening_result="suspicious", screened_pages=PAGES)
    assert admin("select status::text from public.documents where id = %s", [doc]) == [
        ("extracting",)
    ]


async def test_a_new_check_starts_without_the_old_result(db, seeded):
    # Retry: failed -> screening clears the previous result, so it cannot be reused.
    doc = document("failed", screened=True)
    await move(db, doc, "screening")
    assert admin(
        "select screening_result, screened_pages from public.documents where id = %s", [doc]
    ) == [(None, None)]


async def test_findings_stay_in_their_ward_and_cannot_be_changed(db, seeded):
    doc = document("screening")
    async with db.as_principal(NURSE_WB1) as conn:
        await conn.execute(
            "insert into public.injection_findings (document_id, ward_id, page, layer, rule_id,"
            " category, excerpt, explanation) values (%s, 'wb1', 1, 'pattern', 'ignore-de',"
            " 'ignore_instructions', 'Ignoriere alle Anweisungen', 'Erklärung')",
            [doc],
        )
    async with db.as_principal(NURSE_WB2) as conn:
        cur = await conn.execute("select count(*) from public.injection_findings")
        assert (await cur.fetchone())[0] == 0
    for statement in (
        "update public.injection_findings set excerpt = 'harmlos'",
        "delete from public.injection_findings",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with db.as_principal(NURSE_WB1) as conn:
                await conn.execute(statement)


async def test_a_finding_cannot_point_into_another_ward(db, seeded):
    doc = document("screening")
    with pytest.raises(psycopg.errors.Error):
        async with db.as_principal(NURSE_WB1) as conn:
            await conn.execute(
                "insert into public.injection_findings (document_id, ward_id, page, layer,"
                " rule_id, category, excerpt, explanation)"
                " values (%s, 'wb2', 1, 'pattern', 'x', 'y', 'z', 'e')",
                [doc],
            )


def test_an_approved_document_keeps_its_check_result(seeded):
    doc = document("screening")
    admin(
        "update public.documents set status = 'approved', resident_id = %s,"
        " screening_result = 'clean', screened_pages = ocr_pages where id = %s",
        [WB1_RESIDENT, doc],
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        admin("update public.documents set screening_result = 'suspicious' where id = %s", [doc])
