"""F10-AC5 to AC8: the nightly reset and the maintenance mode, against the local database.

The reset runs with admin rights (like the GitHub Action); every check of what visitors
can do runs through the API role.
"""

import asyncio
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.auth.principal import Principal
from app.config import Settings
from app.documents.pipeline import Pipeline, Suggestion
from app.main import create_app
from app.providers.ocr.fake import FakeOcr
from scripts.reset_demo import SEED_DIR, reset
from tests.rls.conftest import ADMIN_DSN, GATEWAY_DSN, WB1_RESIDENT
from tests.support.oidc import (
    AUDIENCE,
    BFF_SECRET,
    ISSUER,
    ROLES_CLAIM,
    access_token,
    bff_assertion,
    test_verifier,
)
from tests.support.screening import FakeScreener

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
SEED_FILES = sorted(SEED_DIR.glob("*.sql"))
COUNTS = (
    "select (select count(*) from public.documents), (select count(*) from public.medications),"
    " (select count(*) from public.medication_events), (select count(*) from public.diagnoses),"
    " (select count(*) from public.follow_ups), (select count(*) from public.residents)"
)


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


@pytest.fixture
def fresh(seeded: None) -> Iterator[tuple]:
    """A freshly reset demo; yields the row counts of the pure seed."""
    reset(ADMIN_DSN, SEED_FILES)
    yield admin(COUNTS)[0]
    admin("update public.system_state set maintenance = false")
    admin("delete from public.usage_counters where subject = 'reset-test'")


def visitor_upload() -> str:
    """What a visitor leaves behind: an upload with its file, a session."""
    doc = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, uploaded_by, upload_session, status)"
        " values (%s, 'wb1', 'u-wb1', 'sid', 'uploaded')",
        [doc],
    )
    admin(
        "insert into public.document_files (document_id, ward_id, mime, size_bytes, content)"
        " values (%s, 'wb1', 'image/jpeg', 4, %s)",
        [doc, b"\xff\xd8\xff\x00"],
    )
    admin(
        "insert into bff.sessions (id_hash, sub, app_role, display_name, tokens_enc,"
        " access_expires_at, expires_at)"
        " values ('h-reset-test', 'u-wb1', 'nurse', 'Pflegekraft WB1', 'x', now(),"
        " now() + interval '1 hour')"
    )
    return doc


def test_reset_removes_visitor_data_and_restores_the_seed(fresh) -> None:  # AC5
    doc = visitor_upload()
    admin(
        "update public.follow_ups set status = 'done', done_by = 'u', done_by_name = 'x',"
        " done_at = now() where status = 'open'"
    )

    reset(ADMIN_DSN, SEED_FILES)

    assert admin("select count(*) from public.documents where id = %s", [doc]) == [(0,)]
    assert admin("select count(*) from public.document_files where document_id = %s", [doc]) == [
        (0,)
    ]
    assert admin("select count(*) from bff.sessions") == [(0,)]
    assert admin("select count(*) > 0 from public.follow_ups where status = 'open'") == [(True,)]
    assert admin(COUNTS)[0] == fresh


def test_reset_empties_the_audit_log(fresh) -> None:  # F12-AC5: the one way to remove events
    admin(
        "insert into public.audit_events (action, outcome, actor_type, actor_sub, actor_name)"
        " values ('question', 'ok', 'human', 'u-wb1', 'Pflegekraft WB1')"
    )
    reset(ADMIN_DSN, SEED_FILES)
    assert admin("select count(*) from public.audit_events") == [(0,)]


def test_reset_removes_the_agents_proposals(fresh) -> None:  # F08: visitor data, too
    admin(
        "insert into public.agent_proposals (ward_id, resident_id, title, created_for)"
        " values ('wb1', %s, 'Kontrolle', 'u-wb1')",
        [WB1_RESIDENT],
    )
    reset(ADMIN_DSN, SEED_FILES)
    assert admin("select count(*) from public.agent_proposals") == [(0,)]


def test_reset_keeps_the_quota_counters_of_the_day(fresh) -> None:  # AC6
    admin(
        "insert into public.usage_counters (period, kind, subject, count)"
        " values (to_char(now() at time zone 'Europe/Berlin', 'YYYY-MM-DD'), 'llm_call',"
        " 'reset-test', 7)"
    )
    reset(ADMIN_DSN, SEED_FILES)
    assert admin("select count from public.usage_counters where subject = 'reset-test'") == [(7,)]


def test_a_failing_reset_changes_nothing_and_ends_maintenance(fresh, tmp_path: Path) -> None:
    doc = visitor_upload()  # AC8
    broken = tmp_path / "99_broken.sql"
    broken.write_text("insert into public.wards (id, name) values ('wb1', 'twice');")

    with pytest.raises(psycopg.Error):
        reset(ADMIN_DSN, [*SEED_FILES, broken])

    assert admin("select count(*) from public.documents where id = %s", [doc]) == [(1,)]
    assert admin("select count(*) from bff.sessions") == [(1,)]
    assert admin("select maintenance from public.system_state") == [(False,)]
    reset(ADMIN_DSN, SEED_FILES)  # a second run is safe
    assert admin(COUNTS)[0] == fresh


def test_two_runs_give_the_same_state(fresh) -> None:  # AC8
    reset(ADMIN_DSN, SEED_FILES)
    reset(ADMIN_DSN, SEED_FILES)
    assert admin(COUNTS)[0] == fresh
    assert admin("select maintenance from public.system_state") == [(False,)]


async def test_the_api_roles_cannot_switch_maintenance(fresh, db) -> None:
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        async with db.as_principal(NURSE_WB1) as conn:
            await conn.execute("update public.system_state set maintenance = true")


# --- AC7: writes during the reset, background work that started before it ---------------
@pytest.fixture
def api(fresh) -> Iterator[TestClient]:
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
    )
    with TestClient(create_app(settings, verifier=test_verifier())) as client:
        yield client


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token('u-wb1', 'nurse_wb1')}",
        "X-Bff-Assertion": bff_assertion(),
    }


def test_writes_are_refused_with_503_during_maintenance(api) -> None:
    (follow_up,) = admin(
        "select id::text from public.follow_ups where resident_id = %s and status = 'open'",
        [WB1_RESIDENT],
    )[0]
    admin("update public.system_state set maintenance = true")

    response = api.post(f"/follow-ups/{follow_up}/done", headers=headers())
    assert response.status_code == 503
    assert response.json() == {
        "error_code": "maintenance",
        "message": "Demo wird gerade zurückgesetzt – bitte in einer Minute erneut versuchen",
    }
    assert api.get("/residents", headers=headers()).status_code == 200  # reading still works

    admin("update public.system_state set maintenance = false")
    assert api.post(f"/follow-ups/{follow_up}/done", headers=headers()).status_code == 200


class WaitingOcr(FakeOcr):
    """OCR that only answers once the test lets it (the reset runs in between)."""

    def __init__(self) -> None:
        super().__init__(default=["# Arztbrief\n\nDiagnose: Hypertonie. Ramipril 5 mg. " * 3])
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def extract(self, data: bytes, mime: str):
        self.started.set()
        await self.release.wait()
        return await super().extract(data, mime)


async def test_processing_that_started_before_the_reset_writes_nothing(fresh, db) -> None:
    doc = visitor_upload()
    ocr = WaitingOcr()

    async def extractor(principal, document_id, text):
        return Suggestion(data={"doc_type": "arztbrief"}, model="fake-llm")

    task = asyncio.create_task(
        Pipeline(db, ocr, extractor, screener=FakeScreener()).run(NURSE_WB1, doc)
    )
    await ocr.started.wait()
    await asyncio.to_thread(reset, ADMIN_DSN, SEED_FILES)
    ocr.release.set()
    await task

    assert admin("select count(*) from public.documents where id = %s", [doc]) == [(0,)]
    assert admin(COUNTS)[0] == fresh
