"""F02-AC4, AC5, AC8, AC9, AC10, AC12, AC13: document endpoints through the whole API stack
(test IdP, BFF assertion, RLS, quotas) with the fake OCR."""

import io
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.config import Settings
from app.main import create_app
from app.providers.llm.fake import FakeLlm
from app.providers.ocr.fake import FakeOcr
from tests.rls.conftest import ADMIN_DSN, GATEWAY_DSN
from tests.support.images import JPEG
from tests.support.oidc import (
    AUDIENCE,
    BFF_SECRET,
    ISSUER,
    ROLES_CLAIM,
    access_token,
    bff_assertion,
    test_verifier,
)

pytestmark = pytest.mark.db


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


@pytest.fixture
def ocr() -> FakeOcr:
    return FakeOcr()


@pytest.fixture
def api(seeded: None, ocr: FakeOcr) -> Iterator[TestClient]:
    admin("truncate public.usage_counters")
    limits = admin("select kind, max_count from public.quota_limits")
    settings = Settings(
        database_url=GATEWAY_DSN,
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_roles_claim=ROLES_CLAIM,
        bff_api_secret=BFF_SECRET,
        llm_provider="fake",  # also the injection checker (F07) is the fake
    )
    app = create_app(settings, verifier=test_verifier(), ocr=ocr, llm=FakeLlm())
    with TestClient(app) as client:
        yield client
    for kind, max_count in limits:
        admin("update public.quota_limits set max_count = %s where kind = %s", [max_count, kind])
    admin("truncate public.usage_counters")


def as_role(role: str, sub: str | None = None, session: str = "session-1") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token(sub or f'u-{role}', role)}",
        "X-Bff-Assertion": bff_assertion(session),
    }


def upload(api, role="nurse_wb1", data=JPEG, session="session-1", **form):
    return api.post(
        "/documents",
        headers=as_role(role, session=session),
        files={"file": ("foto.jpg", data, "image/jpeg")},
        data=form,
    )


def documents_in_db() -> list[tuple]:
    return admin("select ward_id, status::text from public.documents order by created_at")


def test_upload_is_accepted_and_processed_in_the_background(api, ocr):
    response = upload(api)
    assert response.status_code == 202
    doc = response.json()
    assert doc["status"] == "uploaded"
    # TestClient runs background tasks right after the response.
    listed = api.get("/documents", headers=as_role("nurse_wb1")).json()
    assert [(d["id"], d["status"], d["ward_id"]) for d in listed] == [
        (doc["id"], "ready_for_review", "wb1")
    ]
    assert ocr.calls == 1
    session_hash = admin("select upload_session, uploaded_by from public.documents")[0]
    assert session_hash[1] == "u-nurse_wb1" and len(session_hash[0]) == 64


def test_an_invalid_file_is_rejected_before_ocr(api, ocr):
    response = upload(api, data=b"GIF89a" + b"\x00" * 20)
    assert response.status_code == 415
    assert response.json()["error_code"] == "unsupported_type"
    assert "JPEG, PNG oder PDF" in response.json()["message"]
    assert documents_in_db() == [] and ocr.calls == 0


def test_a_pdf_with_too_many_pages_is_rejected(api, ocr):
    writer, buffer = PdfWriter(), io.BytesIO()
    for _ in range(6):
        writer.add_blank_page(width=100, height=100)
    writer.write(buffer)
    response = upload(api, data=buffer.getvalue())
    assert (response.status_code, response.json()["error_code"]) == (422, "too_many_pages")
    assert ocr.calls == 0


def test_empty_daily_quota_rejects_the_upload_without_ocr_and_books_nothing(api, ocr):
    admin("update public.quota_limits set max_count = 0 where kind = 'ocr_page'")
    response = upload(api)
    assert response.status_code == 429
    assert response.json()["error_code"] == "daily_quota"
    assert "Tageskontingent der Demo erreicht" in response.json()["message"]
    assert documents_in_db() == [] and ocr.calls == 0
    assert admin("select count(*) from public.usage_counters") == [(0,)]  # rolled back


def test_sixth_upload_of_a_session_is_refused_another_session_may_upload(api):
    assert [upload(api).status_code for _ in range(5)] == [202] * 5
    sixth = upload(api)
    assert (sixth.status_code, sixth.json()["error_code"]) == (429, "session_upload_limit")
    assert sixth.json()["message"] == "Upload-Limit erreicht – Musterdokumente bleiben nutzbar"
    assert upload(api, session="session-2").status_code == 202


def test_pdl_chooses_the_ward(api):
    assert upload(api, role="pdl", ward_id="wb2").status_code == 202
    assert documents_in_db() == [("wb2", "ready_for_review")]
    missing = upload(api, role="pdl")
    assert (missing.status_code, missing.json()["error_code"]) == (422, "ward_required")


def test_a_nurse_cannot_upload_into_a_foreign_ward(api, ocr):
    response = upload(api, role="nurse_wb1", ward_id="wb2")
    assert response.status_code == 403
    assert documents_in_db() == [] and ocr.calls == 0


def test_the_inbox_shows_only_own_wards(api):
    upload(api, role="nurse_wb1")
    upload(api, role="nurse_wb2")
    wards = {d["ward_id"] for d in api.get("/documents", headers=as_role("nurse_wb2")).json()}
    assert wards == {"wb2"}


def test_foreign_and_unknown_documents_look_the_same(api):
    doc_id = upload(api, role="nurse_wb1").json()["id"]
    wb2 = as_role("nurse_wb2")
    for path in [f"/documents/{doc_id}", f"/documents/{doc_id}/file"]:
        foreign = api.get(path, headers=wb2)
        unknown = api.get(path.replace(doc_id, str(uuid.uuid4())), headers=wb2)
        assert foreign.status_code == unknown.status_code == 404
        assert foreign.json() == unknown.json()
    assert api.get("/documents/kein-uuid", headers=wb2).status_code == 404


def test_document_details_contain_the_ocr_pages(api):
    doc_id = upload(api).json()["id"]
    doc = api.get(f"/documents/{doc_id}", headers=as_role("nurse_wb1")).json()
    assert doc["status"] == "ready_for_review"
    assert doc["ocr_pages"][0]["page"] == 1 and "Arztbrief" in doc["ocr_pages"][0]["markdown"]


def test_the_original_file_is_delivered_with_safe_headers(api):
    doc_id = upload(api).json()["id"]
    response = api.get(f"/documents/{doc_id}/file", headers=as_role("nurse_wb1"))
    assert response.status_code == 200
    assert response.content == JPEG
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == "inline"
    assert "no-store" in response.headers["cache-control"]


def test_retry_continues_a_failed_document(api, ocr):
    ocr.unavailable = True
    doc_id = upload(api).json()["id"]
    failed = api.get(f"/documents/{doc_id}", headers=as_role("nurse_wb1")).json()
    assert (failed["status"], failed["error_code"]) == ("failed", "ocr_unavailable")

    ocr.unavailable = False
    assert api.post(f"/documents/{doc_id}/retry", headers=as_role("nurse_wb1")).status_code == 202
    assert api.get(f"/documents/{doc_id}", headers=as_role("nurse_wb1")).json()["status"] == (
        "ready_for_review"
    )
    again = api.post(f"/documents/{doc_id}/retry", headers=as_role("nurse_wb1"))
    assert again.status_code == 409


def test_retry_books_the_quota_again(api, ocr):
    ocr.unavailable = True
    doc_id = upload(api).json()["id"]
    admin("update public.quota_limits set max_count = 1 where kind = 'llm_call'")
    response = api.post(f"/documents/{doc_id}/retry", headers=as_role("nurse_wb1"))
    assert (response.status_code, response.json()["error_code"]) == (429, "daily_quota")
    assert ocr.calls == 1  # only the upload's attempt


def test_retry_of_a_foreign_document_is_not_found(api, ocr):
    ocr.unavailable = True
    doc_id = upload(api, role="nurse_wb1").json()["id"]
    assert api.post(f"/documents/{doc_id}/retry", headers=as_role("nurse_wb2")).status_code == 404


def test_listing_the_inbox_marks_stalled_documents(api):
    doc_id = upload(api).json()["id"]
    admin(
        "update public.documents set status = 'processing',"
        " status_changed_at = now() - interval '6 minutes' where id = %s",
        [doc_id],
    )
    listed = api.get("/documents", headers=as_role("nurse_wb1")).json()
    assert (listed[0]["status"], listed[0]["error_code"]) == ("failed", "timeout")


def test_uploads_need_the_bff_assertion(api):
    response = api.post(
        "/documents",
        headers={"Authorization": f"Bearer {access_token('u', 'nurse_wb1')}"},
        files={"file": ("foto.jpg", JPEG, "image/jpeg")},
    )
    assert response.status_code == 401


def test_the_suggestion_is_stored_with_the_model(api):
    doc_id = upload(api).json()["id"]
    doc = api.get(f"/documents/{doc_id}", headers=as_role("nurse_wb1")).json()
    assert doc["suggestion_model"] == "fake-llm (Testattrappe)"
    assert doc["suggestion"]["doc_type"]["value"] == "arztbrief"
    assert doc["suggestion"]["medications"][0]["evidence_found"] is True
