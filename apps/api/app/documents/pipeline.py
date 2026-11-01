"""Background processing of an accepted document as a state machine (F02-AC6 to F02-AC9).

    uploaded -> processing -> screening -> extracting -> ready_for_review
                     \\-> unreadable          (readability check, end state)
    uploaded | processing | screening | extracting -> failed (error_code)
    failed -> processing (no OCR result yet) | screening (OCR result kept)  = retry

`screening` is the injection check (F07): the field suggestion only gets the cleaned pages
it produces. The database refuses `extracting` without it (trigger documents_require_screening).

Every status change is a conditional update ("... where status = <expected>"). If the
document changed in between - a parallel retry, or the inbox marked it as stalled - the
update matches no row and this run stops without overwriting anything.

All database access runs as the uploading user (RLS applies); OCR and extraction run
outside any transaction, so no database connection is held for minutes.

Every model step writes its event for the audit log after the call (F12, app/audit.py).
If that event cannot be written, the step's result is not used: the document fails.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import get_args

from psycopg.types.json import Jsonb

from app import audit
from app.auth.principal import Principal
from app.db import Database
from app.documents.readability import check_readability
from app.extraction.schema import DocType
from app.privacy.gateway import PseudonymizationFailed
from app.providers.llm.base import LlmUnavailable
from app.providers.ocr.base import OcrProvider, OcrUnavailable
from app.quotas import QuotaExceeded
from app.security.screening import Screener, Screening

log = logging.getLogger(__name__)

# F02-AC8: a step that takes longer than 5 minutes fails with "timeout"
# (PIPELINE_STEP_SECONDS, longer only in the fully local mode).
STEP_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class Suggestion:
    """Result of the extraction (F03); data None = "Kein Vorschlag möglich" (F03-AC2)."""

    data: dict | None
    model: str | None


Extractor = Callable[[Principal, str, str], Awaitable[Suggestion]]


async def no_suggestion(principal: Principal, document_id: str, text: str) -> Suggestion:
    """Default until F03: no field suggestion, the document still becomes reviewable."""
    return Suggestion(data=None, model=None)


def joined_text(pages: list[dict]) -> str:
    return "\n\n".join(page["markdown"] for page in pages)


class Pipeline:
    def __init__(
        self,
        db: Database,
        ocr: OcrProvider,
        extractor: Extractor = no_suggestion,
        step_timeout: float = STEP_TIMEOUT_SECONDS,
        *,
        screener: Screener,  # required on purpose: there is no pipeline without the check
    ):
        self.db = db
        self.ocr = ocr
        self.extractor = extractor
        self.step_timeout = step_timeout
        self.screener = screener

    async def run(self, principal: Principal, document_id: str) -> None:
        """Processes a new or failed document from the step where it stopped."""
        async with self.db.as_principal(principal) as conn:
            cur = await conn.execute(
                "select status::text, ocr_pages from public.documents where id = %s",
                [document_id],
            )
            row = await cur.fetchone()
        if row is None:  # unknown or another ward's document (RLS)
            return
        status, pages = row
        if status == "uploaded" or (status == "failed" and pages is None):
            pages = await self._ocr_step(principal, document_id, from_status=status)
        elif status == "failed":
            # Every retry after the OCR checks again (F07-AC1); the trigger clears the old result.
            if not await self._move(principal, document_id, "failed", "screening", attempt=True):
                return
        else:
            return  # in progress elsewhere or past processing: nothing to do
        if pages is None:
            return
        screened = await self._screening_step(principal, document_id, pages)
        if screened is not None:
            await self._extraction_step(principal, document_id, joined_text(screened))

    async def _ocr_step(self, principal: Principal, doc: str, from_status: str) -> list | None:
        if not await self._move(principal, doc, from_status, "processing", attempt=True):
            return None
        async with self.db.as_principal(principal) as conn:
            cur = await conn.execute(
                "select content, mime from public.document_files where document_id = %s", [doc]
            )
            content, mime = await cur.fetchone()
        try:
            result = await asyncio.wait_for(self.ocr.extract(content, mime), self.step_timeout)
        except TimeoutError:
            await self._step_failed(
                principal, doc, "ocr", self.ocr.model_name, "processing", "timeout"
            )
            return None
        except OcrUnavailable as error:
            log.warning("OCR unavailable for %s: %s", doc, error)
            await self._step_failed(
                principal, doc, "ocr", self.ocr.model_name, "processing", "ocr_unavailable"
            )
            return None
        except Exception:
            log.exception("OCR step crashed for %s", doc)
            await self._step_failed(
                principal, doc, "ocr", self.ocr.model_name, "processing", "ocr_unavailable"
            )
            return None
        numbers = [page.number for page in result.pages]
        if not await self._audit(principal, doc, "ocr", model=self.ocr.model_name, pages=numbers):
            await self._fail(principal, doc, "processing", "ocr_unavailable")
            return None

        readability = check_readability(result.text)
        if not readability.readable:
            await self._move(
                principal, doc, "processing", "unreadable", error_code=readability.error_code
            )
            return None
        pages = [{"page": page.number, "markdown": page.markdown} for page in result.pages]
        if not await self._move(principal, doc, "processing", "screening", ocr_pages=pages):
            return None
        return pages

    async def _screening_step(self, principal: Principal, doc: str, pages: list) -> list | None:
        """F07: hidden text, rules, checker model. Returns the cleaned pages or None."""
        async with self.db.as_principal(principal) as conn:
            cur = await conn.execute(
                "select content, mime from public.document_files where document_id = %s", [doc]
            )
            content, mime = await cur.fetchone()
        pdf = bytes(content) if mime == "application/pdf" else None
        try:
            screening = await asyncio.wait_for(
                self.screener(principal, pages, pdf), self.step_timeout
            )
        except TimeoutError:
            await self._step_failed(
                principal, doc, "screening", self.screener.model_name, "screening", "timeout"
            )
            return None
        except QuotaExceeded as exceeded:
            await self._quota_exhausted(principal, doc, "screening", exceeded)
            return None
        except PseudonymizationFailed:
            log.warning("pseudonymization refused for the check of %s", doc)
            await self._pseudonymization_refused(principal, doc, "screening")
            return None
        except Exception:  # checker unreachable or anything else: never go on unchecked
            log.exception("injection check failed for %s", doc)
            await self._step_failed(
                principal, doc, "screening", self.screener.model_name, "screening",
                "screening_unavailable",
            )  # fmt: skip
            return None
        if not await self._log_screening(principal, doc, screening):
            await self._fail(principal, doc, "screening", "screening_unavailable")
            return None
        if not await self._finish_screening(principal, doc, screening):
            return None
        return screening.screened_pages

    async def _log_screening(self, principal: Principal, doc: str, screening: Screening) -> bool:
        """The check, then one `blocked` event per finding: layer and rule, no text (F07-AC11)."""
        outcome = "blocked" if screening.findings else "ok"
        if not await self._audit(
            principal, doc, "screening", outcome, model=self.screener.model_name
        ):
            return False
        for f in screening.findings:
            if not await self._audit(
                principal, doc, "blocked", "blocked", layer=f.layer, rule_id=f.rule_id,
                pages=[f.page],
            ):  # fmt: skip
                return False
        return True

    async def _finish_screening(self, principal: Principal, doc: str, screening: Screening) -> bool:
        """Result, cleaned pages and findings in one transaction, then on to extracting."""
        async with self.db.as_principal(principal) as conn:
            cur = await conn.execute(
                "update public.documents set status = 'extracting', status_changed_at = now(),"
                " screening_result = %s, screened_pages = %s"
                " where id = %s and status = 'screening' returning ward_id",
                [screening.result, Jsonb(screening.screened_pages), doc],
            )
            row = await cur.fetchone()
            if row is None:  # changed meanwhile (stalled, parallel retry)
                return False
            for f in screening.findings:
                await conn.execute(
                    "insert into public.injection_findings (document_id, ward_id, page,"
                    " start_offset, end_offset, layer, rule_id, category, excerpt, explanation)"
                    " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        doc,
                        row[0],
                        f.page,
                        f.start,
                        f.end,
                        f.layer,
                        f.rule_id,
                        f.category,
                        f.excerpt,
                        f.explanation,
                    ],
                )
        return True

    async def _extraction_step(self, principal: Principal, doc: str, text: str) -> None:
        try:
            suggestion = await asyncio.wait_for(
                self.extractor(principal, doc, text), self.step_timeout
            )
        except TimeoutError:
            await self._step_failed(
                principal, doc, "extraction", self._extraction_model, "extracting", "timeout"
            )
            return
        except QuotaExceeded as exceeded:
            await self._quota_exhausted(principal, doc, "extracting", exceeded)
            return
        except LlmUnavailable as error:
            log.warning("LLM unavailable for %s: %s", doc, error)
            await self._step_failed(
                principal,
                doc,
                "extraction",
                self._extraction_model,
                "extracting",
                "llm_unavailable",
            )
            return
        except PseudonymizationFailed:
            # F06-AC10: a plain name was still in the text - nothing was sent.
            log.warning("pseudonymization refused for %s", doc)
            await self._pseudonymization_refused(principal, doc, "extracting")
            return
        except Exception:
            log.exception("extraction step crashed for %s", doc)
            await self._step_failed(
                principal,
                doc,
                "extraction",
                self._extraction_model,
                "extracting",
                "llm_unavailable",
            )
            return
        if not await self._audit(principal, doc, "extraction", model=suggestion.model):
            await self._fail(principal, doc, "extracting", "llm_unavailable")
            return
        await self._move(principal, doc, "extracting", "ready_for_review", suggestion=suggestion)

    @staticmethod
    def recognised_type(suggestion: Suggestion | None) -> str | None:
        """The document type, if the extraction verified it in the text (F02-AC13: the inbox
        shows it before the approval). An unverified guess stays out."""
        field = (suggestion.data or {}).get("doc_type") if suggestion else None
        value = field.get("value") if isinstance(field, dict) else None
        return value if value in get_args(DocType) else None

    async def _audit(self, principal: Principal, doc: str, action: str, outcome="ok", **kw) -> bool:
        """Writes one event; False if that failed (the caller then drops the result)."""
        try:
            await audit.log(self.db, principal, action, outcome, document_id=doc, **kw)
        except audit.AuditFailed:
            log.exception("audit event %s for %s could not be written", action, doc)
            return False
        return True

    @property
    def _extraction_model(self) -> str | None:
        # The default `no_suggestion` calls no model and has no name.
        return getattr(self.extractor, "model_name", None)

    async def _step_failed(self, principal, doc, action, model, from_status, code) -> None:
        # The document fails either way; a missing event does not change that.
        await self._audit(principal, doc, action, "error", model=model, error_code=code)
        await self._fail(principal, doc, from_status, code)

    async def _quota_exhausted(self, principal, doc, from_status, exceeded: QuotaExceeded) -> None:
        await self._audit(principal, doc, "quota_exhausted", "blocked", error_code=exceeded.kind)
        await self._fail(principal, doc, from_status, "quota_exceeded")

    async def _pseudonymization_refused(self, principal, doc, from_status) -> None:
        code = "pseudonymization_failed"
        await self._audit(principal, doc, "blocked", "blocked", error_code=code)
        await self._fail(principal, doc, from_status, code)

    async def _fail(self, principal: Principal, doc: str, from_status: str, code: str) -> None:
        await self._move(principal, doc, from_status, "failed", error_code=code)

    async def _move(
        self,
        principal: Principal,
        doc: str,
        from_status: str,
        to_status: str,
        *,
        error_code: str | None = None,
        attempt: bool = False,
        ocr_pages: list | None = None,
        suggestion: Suggestion | None = None,
    ) -> bool:
        """Conditional status change; False if the document is no longer in from_status."""
        async with self.db.as_principal(principal) as conn:
            cur = await conn.execute(
                """
                update public.documents set
                  status = %(to)s::public.document_status,
                  error_code = %(error_code)s,
                  status_changed_at = now(),
                  attempts = attempts + %(attempt)s,
                  ocr_pages = coalesce(%(pages)s, ocr_pages),
                  suggestion = case when %(set_suggestion)s then %(suggestion)s else suggestion end,
                  suggestion_model = case when %(set_suggestion)s then %(model)s
                                          else suggestion_model end,
                  doc_type = coalesce(%(doc_type)s::public.doc_type, doc_type)
                where id = %(id)s and status = %(from)s::public.document_status
                returning id
                """,
                {
                    "to": to_status,
                    "from": from_status,
                    "id": doc,
                    "error_code": error_code,
                    "attempt": 1 if attempt else 0,
                    "pages": Jsonb(ocr_pages) if ocr_pages is not None else None,
                    "set_suggestion": suggestion is not None,
                    "suggestion": Jsonb(suggestion.data)
                    if suggestion and suggestion.data
                    else None,
                    "model": suggestion.model if suggestion else None,
                    "doc_type": self.recognised_type(suggestion),
                },
            )
            return await cur.fetchone() is not None


async def mark_stalled(
    db: Database, principal: Principal, step_seconds: int = STEP_TIMEOUT_SECONDS
) -> None:
    """F02-AC9: documents stuck after a restart become failed/timeout instead of "in progress".

    Runs before the inbox is listed; RLS limits it to the caller's wards. "uploaded" for more
    than 2 minutes means the background task never started (crash right after the upload).
    """
    async with db.as_principal(principal) as conn:
        await conn.execute(
            """
            update public.documents
            set status = 'failed', error_code = 'timeout', status_changed_at = now()
            where (status = 'uploaded' and status_changed_at < now() - interval '2 minutes')
               or (status in ('processing', 'screening', 'extracting')
                   and status_changed_at < now() - make_interval(secs => %s))
            """,
            [step_seconds],
        )
