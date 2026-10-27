"""OCR providers; `create_ocr_provider` picks one from OCR_PROVIDER (F02-AC11)."""

from app.config import Settings
from app.providers.ocr.base import OcrProvider, OcrResult, OcrUnavailable, Page
from app.providers.ocr.docling import DoclingOcr
from app.providers.ocr.fake import FakeOcr

__all__ = ["OcrProvider", "OcrResult", "OcrUnavailable", "Page", "create_ocr_provider"]


def create_ocr_provider(settings: Settings) -> OcrProvider:
    if settings.ocr_provider == "docling":
        return DoclingOcr(settings.docling_base_url)
    if settings.ocr_provider == "fake":
        return FakeOcr()
    raise ValueError(f"OCR provider {settings.ocr_provider!r} is not available")
