"""Docling (local OCR, F02-AC11). Stage 1: interface only, the service follows in phase 8."""

from app.providers.ocr.base import OcrResult, OcrUnavailable


class DoclingOcr:
    model_name = "docling"

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def extract(self, data: bytes, mime: str) -> OcrResult:
        # Fails loudly instead of returning nothing: an empty result would look "unreadable".
        raise OcrUnavailable("Docling ist in Stufe 1 noch nicht angebunden")
