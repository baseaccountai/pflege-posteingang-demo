"""Mistral OCR (public demo, F02-AC6). The file goes to Mistral as a base64 data URL.

Known limit, named in the app and the threat model: in cloud mode Mistral OCR sees the raw
document. Every failure (network, timeout, HTTP error, unexpected answer) becomes
OcrUnavailable, so the pipeline can set failed/ocr_unavailable and offer a retry (F02-AC8).
"""

import base64

import httpx

from app.providers.ocr.base import OcrResult, OcrUnavailable, Page

OCR_URL = "https://api.mistral.ai/v1/ocr"
TIMEOUT_SECONDS = 60


class MistralOcr:
    def __init__(self, api_key: str, model: str, timeout: float = TIMEOUT_SECONDS):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def extract(self, data: bytes, mime: str) -> OcrResult:
        if not self.api_key:
            raise OcrUnavailable("MISTRAL_API_KEY is not set")
        data_url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        kind = "document_url" if mime == "application/pdf" else "image_url"
        body = {
            "model": self.model,
            "document": {"type": kind, kind: data_url},
            "include_image_base64": False,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    OCR_URL, json=body, headers={"authorization": f"Bearer {self.api_key}"}
                )
            response.raise_for_status()
            pages = response.json()["pages"]
            ordered = sorted(pages, key=lambda page: page["index"])
            # Numbered 1..n by order; Mistral's own index base is not relied upon.
            return OcrResult(
                pages=[Page(number=i, markdown=p["markdown"]) for i, p in enumerate(ordered, 1)]
            )
        except httpx.HTTPStatusError as error:
            # Only the status code: the request (with the key header) is never logged.
            raise OcrUnavailable(f"Mistral OCR answered {error.response.status_code}") from None
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
            raise OcrUnavailable(f"Mistral OCR failed: {type(error).__name__}") from None
