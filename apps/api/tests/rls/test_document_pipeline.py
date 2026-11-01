"""F02-AC6, F02-AC7, F02-AC8, F02-AC9: processing as a state machine, with stand-ins for
OCR and extraction, against the local database (as the uploading user, under RLS)."""

import asyncio
import uuid

import psycopg
import pytest

from app.auth.principal import Principal
from app.documents.pipeline import Pipeline, Suggestion, mark_stalled
from app.privacy.gateway import PseudonymizationFailed
from app.providers.llm.base import LlmUnavailable
from app.providers.ocr.fake import FakeOcr
from app.quotas import QuotaExceeded
from tests.rls.conftest import ADMIN_DSN
from tests.support.screening import FakeScreener

pytestmark = [pytest.mark.db, pytest.mark.anyio]

NURSE_WB1 = Principal(
    sub="u-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Pflegekraft WB1"
)
NURSE_WB2 = Principal(
    sub="u-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Pflegekraft WB2"
)
READABLE = ["# Arztbrief\n\nDiagnose: Hypertonie. Medikation: Ramipril 5 mg 1-0-0-0. " * 2]


def admin(sql: str, params: list | None = None) -> list[tuple]:
    with psycopg.connect(ADMIN_DSN, autocommit=True) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def new_document(ward: str = "wb1", status: str = "uploaded", age_minutes: int = 0) -> str:
    doc_id = str(uuid.uuid4())
    admin(
        "insert into public.documents (id, ward_id, uploaded_by, upload_session, status,"
        " status_changed_at)"
        " values (%s, %s, 'u-wb1', 'sid', %s, now() - make_interval(mins => %s))",
        [doc_id, ward, status, age_minutes],
    )
    admin(
        "insert into public.document_files (document_id, ward_id, mime, size_bytes, content)"
        " values (%s, %s, 'image/jpeg', 4, %s)",
        [doc_id, ward, b"\xff\xd8\xff\x00"],
    )
    return doc_id


def state(doc_id: str) -> tuple:
    return admin(
        "select status::text, error_code, attempts, ocr_pages, suggestion, suggestion_model"
        " from public.documents where id = %s",
        [doc_id],
    )[0]


class FakeExtractor:
    model_name = "fake-llm"

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[str, str, str]] = []  # (document, text, status at call time)

    async def __call__(self, principal: Principal, document_id: str, text: str) -> Suggestion:
        self.calls.append((document_id, text, state(document_id)[0]))
        if self.error:
            raise self.error
        return Suggestion(data={"doc_type": "arztbrief"}, model="fake-llm")


class StatusRecordingOcr(FakeOcr):
    """Remembers the document status at the moment OCR runs (must be 'processing')."""

    def __init__(self, doc_id: str, **kwargs):
        super().__init__(default=READABLE, **kwargs)
        self.doc_id = doc_id
        self.seen: list[str] = []

    async def extract(self, data: bytes, mime: str):
        self.seen.append(state(self.doc_id)[0])
        return await super().extract(data, mime)


async def test_success_runs_ocr_then_extraction_then_ready_for_review(db, seeded):
    doc = new_document()
    ocr, extractor = StatusRecordingOcr(doc), FakeExtractor()
    await Pipeline(db, ocr, extractor, screener=FakeScreener()).run(NURSE_WB1, doc)

    status, error, attempts, pages, suggestion, model = state(doc)
    assert (status, error, attempts) == ("ready_for_review", None, 1)
    assert pages == [{"page": 1, "markdown": READABLE[0]}]
    assert (suggestion, model) == ({"doc_type": "arztbrief"}, "fake-llm")
    assert ocr.seen == ["processing"]
    assert [(d, s) for d, _, s in extractor.calls] == [(doc, "extracting")]
    assert extractor.calls[0][1] == READABLE[0]


async def test_ocr_outage_fails_and_the_retry_starts_again_with_ocr(db, seeded):
    doc = new_document()
    await Pipeline(db, FakeOcr(unavailable=True), FakeExtractor(), screener=FakeScreener()).run(
        NURSE_WB1, doc
    )
    assert state(doc)[:4] == ("failed", "ocr_unavailable", 1, None)

    ocr, extractor = FakeOcr(default=READABLE), FakeExtractor()
    await Pipeline(db, ocr, extractor, screener=FakeScreener()).run(NURSE_WB1, doc)
    assert state(doc)[:3] == ("ready_for_review", None, 2)
    assert ocr.calls == 1 and len(extractor.calls) == 1


async def test_a_refused_pseudonymization_fails_the_document_with_its_own_code(db, seeded):
    # F06-AC10: no model call with plain names; the visitor sees why.
    doc = new_document()
    extractor = FakeExtractor(PseudonymizationFailed())
    await Pipeline(db, FakeOcr(default=READABLE), extractor, screener=FakeScreener()).run(
        NURSE_WB1, doc
    )
    assert state(doc)[:2] == ("failed", "pseudonymization_failed")


async def test_llm_outage_keeps_the_ocr_result_and_the_retry_only_extracts(db, seeded):
    doc = new_document()
    await Pipeline(
        db, FakeOcr(default=READABLE), FakeExtractor(LlmUnavailable()), screener=FakeScreener()
    ).run(NURSE_WB1, doc)
    status, error, _, pages, _, _ = state(doc)
    assert (status, error) == ("failed", "llm_unavailable")
    assert pages == [{"page": 1, "markdown": READABLE[0]}]

    ocr, extractor = FakeOcr(default=READABLE), FakeExtractor()
    await Pipeline(db, ocr, extractor, screener=FakeScreener()).run(NURSE_WB1, doc)
    assert state(doc)[0] == "ready_for_review"
    assert ocr.calls == 0  # OCR result reused, no second OCR cost
    assert [s for _, _, s in extractor.calls] == ["extracting"]


async def test_quota_running_out_during_processing_fails_with_quota_exceeded(db, seeded):
    doc = new_document()
    await Pipeline(
        db,
        FakeOcr(default=READABLE),
        FakeExtractor(QuotaExceeded("llm_call")),
        screener=FakeScreener(),
    ).run(NURSE_WB1, doc)
    assert state(doc)[:2] == ("failed", "quota_exceeded")


@pytest.mark.parametrize(
    ("texts", "code"),
    [([""], "unreadable_text"), (["Apfelkuchen mit Zimt und Zucker. " * 5], "not_care_document")],
)
async def test_unreadable_text_ends_without_extraction(db, seeded, texts, code):
    doc = new_document()
    extractor = FakeExtractor()
    await Pipeline(db, FakeOcr(default=texts), extractor, screener=FakeScreener()).run(
        NURSE_WB1, doc
    )
    assert state(doc)[:2] == ("unreadable", code)
    assert extractor.calls == []


@pytest.mark.parametrize("status", ["unreadable", "ready_for_review", "approved", "rejected"])
async def test_documents_past_processing_are_left_alone(db, seeded, status):
    doc = new_document(status=status)
    ocr, extractor = FakeOcr(), FakeExtractor()
    await Pipeline(db, ocr, extractor, screener=FakeScreener()).run(NURSE_WB1, doc)
    assert state(doc)[0] == status
    assert ocr.calls == 0 and extractor.calls == []


async def test_a_step_longer_than_the_limit_fails_with_timeout(db, seeded):
    class HangingOcr(FakeOcr):
        async def extract(self, data, mime):
            await asyncio.sleep(10)

    doc = new_document()
    await Pipeline(
        db, HangingOcr(), FakeExtractor(), step_timeout=0.2, screener=FakeScreener()
    ).run(NURSE_WB1, doc)
    assert state(doc)[:2] == ("failed", "timeout")


async def test_a_late_ocr_answer_does_not_overwrite_a_timeout(db, seeded):
    doc = new_document()

    class SlowOcr(FakeOcr):
        async def extract(self, data, mime):
            # Meanwhile the inbox marks the document as stalled (F02-AC9).
            admin(
                "update public.documents set status = 'failed', error_code = 'timeout'"
                " where id = %s",
                [doc],
            )
            return await super().extract(data, mime)

    extractor = FakeExtractor()
    await Pipeline(db, SlowOcr(default=READABLE), extractor, screener=FakeScreener()).run(
        NURSE_WB1, doc
    )
    assert state(doc)[:2] == ("failed", "timeout")
    assert state(doc)[3] is None and extractor.calls == []


async def test_stalled_documents_are_marked_as_timeout(db, seeded):
    stuck_upload = new_document(status="uploaded", age_minutes=3)
    fresh_upload = new_document(status="uploaded", age_minutes=1)
    stuck_ocr = new_document(status="processing", age_minutes=6)
    busy_extraction = new_document(status="extracting", age_minutes=4)
    stuck_extraction = new_document(status="extracting", age_minutes=6)
    other_ward = new_document(ward="wb2", status="processing", age_minutes=30)

    await mark_stalled(db, NURSE_WB1)

    assert state(stuck_upload)[:2] == ("failed", "timeout")
    assert state(fresh_upload)[0] == "uploaded"
    assert state(stuck_ocr)[:2] == ("failed", "timeout")
    assert state(busy_extraction)[0] == "extracting"
    assert state(stuck_extraction)[:2] == ("failed", "timeout")
    assert state(other_ward)[0] == "processing"  # RLS: WB1 cannot touch WB2


async def test_the_local_mode_waits_longer_before_a_document_counts_as_stalled(db, seeded):
    # F02-AC8/AC9 with PIPELINE_STEP_SECONDS: qwen3:8b needs ~13 min for a suggestion on a
    # laptop CPU (01.11.2026); the public demo keeps its 5 minutes.
    busy = new_document(status="extracting", age_minutes=20)
    stuck = new_document(status="extracting", age_minutes=31)
    await mark_stalled(db, NURSE_WB1, step_seconds=1800)
    assert state(busy)[0] == "extracting"
    assert state(stuck)[:2] == ("failed", "timeout")


async def test_retry_after_a_crash_before_ocr_starts_with_ocr(db, seeded):
    doc = new_document(status="uploaded", age_minutes=3)
    await mark_stalled(db, NURSE_WB1)
    ocr = FakeOcr(default=READABLE)
    await Pipeline(db, ocr, FakeExtractor(), screener=FakeScreener()).run(NURSE_WB1, doc)
    assert state(doc)[0] == "ready_for_review" and ocr.calls == 1


async def test_another_ward_cannot_process_the_document(db, seeded):
    doc = new_document(ward="wb1")
    ocr = FakeOcr(default=READABLE)
    await Pipeline(db, ocr, FakeExtractor(), screener=FakeScreener()).run(NURSE_WB2, doc)
    assert state(doc)[0] == "uploaded" and ocr.calls == 0


class TypedExtractor(FakeExtractor):
    """Suggestion in the real shape (app.extraction.service): value is None if not verified."""

    def __init__(self, doc_type: str | None):
        super().__init__()
        self.doc_type = doc_type

    async def __call__(self, principal: Principal, document_id: str, text: str) -> Suggestion:
        field = {
            "value": self.doc_type,
            "proposed": "medikationsplan",
            "evidence_found": bool(self.doc_type),
        }
        return Suggestion(data={"doc_type": field}, model="fake-llm")


# Codex review Phase 3 #7, F02-AC13: the inbox shows the type as soon as it is recognised,
# not only after the approval.
@pytest.mark.parametrize(
    ("recognised", "expected"), [("medikationsplan", "medikationsplan"), (None, None)]
)
async def test_a_recognised_type_is_stored_on_the_document(db, seeded, recognised, expected):
    doc = new_document()
    await Pipeline(
        db, FakeOcr(default=READABLE), TypedExtractor(recognised), screener=FakeScreener()
    ).run(NURSE_WB1, doc)
    assert admin("select doc_type::text from public.documents where id = %s", [doc]) == [
        (expected,)
    ]


# --- F07: the injection check between OCR and field suggestion -------------------------------


class StatusRecordingScreener(FakeScreener):
    async def __call__(self, principal, pages, pdf):
        self.statuses.append(state(self.doc)[0])
        return await super().__call__(principal, pages, pdf)


async def test_the_check_runs_in_its_own_status_before_the_suggestion(db, seeded):
    doc = new_document()
    screener, extractor = StatusRecordingScreener(), FakeExtractor()
    screener.doc = doc
    await Pipeline(db, FakeOcr(default=READABLE), extractor, screener=screener).run(NURSE_WB1, doc)
    assert screener.statuses == ["screening"]
    assert state(doc)[0] == "ready_for_review"
    assert admin("select screening_result from public.documents where id = %s", [doc]) == [
        ("clean",)
    ]


async def test_findings_are_stored_and_only_the_cleaned_text_goes_on(db, seeded):
    from app.security.screening import EXCLUDED, Finding, Screening

    doc = new_document()
    cleaned = [{"page": 1, "markdown": f"# Arztbrief\n\n{EXCLUDED}"}]
    finding = Finding(
        1, 13, 40, "pattern", "address-de", "addresses_ai", "Hinweis für das KI-System", "Erklärung"
    )
    screener = FakeScreener(result=Screening("suspicious", cleaned, [finding]))
    extractor = FakeExtractor()
    await Pipeline(db, FakeOcr(default=READABLE), extractor, screener=screener).run(NURSE_WB1, doc)
    assert extractor.calls[0][1] == cleaned[0]["markdown"]
    assert admin(
        "select screening_result, screened_pages from public.documents where id = %s", [doc]
    ) == [("suspicious", cleaned)]
    assert admin(
        "select page, start_offset, layer, rule_id, excerpt from public.injection_findings"
        " where document_id = %s",
        [doc],
    ) == [(1, 13, "pattern", "address-de", "Hinweis für das KI-System")]


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (LlmUnavailable("down"), "screening_unavailable"),
        (RuntimeError("anything"), "screening_unavailable"),
        (QuotaExceeded("guard_document"), "quota_exceeded"),
        (PseudonymizationFailed(), "pseudonymization_failed"),
    ],
    ids=["checker-down", "crash", "quota", "plain-name"],
)
async def test_without_a_check_nothing_goes_on(db, seeded, error, code):
    # F07-AC7: fail closed - no suggestion for an unchecked document.
    doc = new_document()
    extractor = FakeExtractor()
    await Pipeline(db, FakeOcr(default=READABLE), extractor, screener=FakeScreener(error)).run(
        NURSE_WB1, doc
    )
    assert state(doc)[:2] == ("failed", code)
    assert extractor.calls == []


async def test_a_retry_after_the_ocr_checks_again(db, seeded):
    doc = new_document()
    await Pipeline(
        db, FakeOcr(default=READABLE), FakeExtractor(), screener=FakeScreener(LlmUnavailable("x"))
    ).run(NURSE_WB1, doc)
    ocr, screener, extractor = FakeOcr(default=READABLE), FakeScreener(), FakeExtractor()
    await Pipeline(db, ocr, extractor, screener=screener).run(NURSE_WB1, doc)
    assert ocr.calls == 0 and len(screener.calls) == 1 and len(extractor.calls) == 1
    assert state(doc)[0] == "ready_for_review"


async def test_a_pdf_is_handed_to_the_check_for_hidden_text(db, seeded):
    doc = new_document()
    admin(
        "update public.document_files set mime = 'application/pdf', content = %s"
        " where document_id = %s",
        [b"%PDF-1.4 fake", doc],
    )
    screener = FakeScreener()
    await Pipeline(db, FakeOcr(default=READABLE), FakeExtractor(), screener=screener).run(
        NURSE_WB1, doc
    )
    assert screener.calls[0][1] == b"%PDF-1.4 fake"


async def test_a_document_stuck_in_the_check_is_marked_stalled(db, seeded):
    doc = new_document(status="screening", age_minutes=6)
    await mark_stalled(db, NURSE_WB1)
    assert state(doc)[:2] == ("failed", "timeout")
