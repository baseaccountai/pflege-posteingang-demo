"""Docling (local OCR, F02-AC11, F11-AC17): docling-serve on the own machine.

The file never leaves the computer - the counterpart to Mistral OCR, which sees the raw
document in cloud mode. docling-serve returns one Markdown text for the whole document; a
fixed placeholder between the pages lets us cut it into pages like Mistral's answer.

Every failure (service stopped, timeout, HTTP error, unexpected answer, a conversion that
did not fully succeed) becomes OcrUnavailable: failed/ocr_unavailable, retry offered (F02-AC8).
"""

import httpx

from app.providers.ocr.base import OcrResult, OcrUnavailable, Page

PAGE_BREAK = "<!-- seitenumbruch -->"
# Measured on a laptop CPU without GPU: a PDF page ~15 s, a phone photo ~30 s (01.11.2026).
TIMEOUT_SECONDS = 180
EXTENSIONS = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}


class DoclingOcr:
    model_name = "docling"

    def __init__(self, base_url: str, timeout: float = TIMEOUT_SECONDS):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def extract(self, data: bytes, mime: str) -> OcrResult:
        name = f"dokument.{EXTENSIONS.get(mime, 'bin')}"
        options = {
            "to_formats": "md",
            "image_export_mode": "placeholder",  # no pictures in the text
            "md_page_break_placeholder": PAGE_BREAK,
            "ocr_lang": "de",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/convert/file",
                    files={"files": (name, data, mime)},
                    data=options,
                )
            response.raise_for_status()
            answer = response.json()
            if answer["status"] != "success":  # also "partial_success": pages may be missing
                raise OcrUnavailable(f"Docling: {answer['status']}")
            markdown = answer["document"]["md_content"]
        except httpx.HTTPStatusError as error:
            raise OcrUnavailable(f"Docling answered {error.response.status_code}") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise OcrUnavailable(f"Docling failed: {type(error).__name__}") from None
        pages = [part.strip() for part in markdown.split(PAGE_BREAK)]
        return OcrResult(pages=[Page(number=i, markdown=md) for i, md in enumerate(pages, 1)])
