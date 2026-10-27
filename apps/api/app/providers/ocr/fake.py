"""OCR stand-in for tests and the end-to-end run without a Mistral key (OCR_PROVIDER=fake).

Answers with the Markdown registered for a file (by SHA-256) or with a default text, so a
test can decide what the "OCR" reads. Never used in the public demo.
"""

import hashlib

from app.providers.ocr.base import OcrResult, OcrUnavailable, Page

# Readable care document, long enough for the readability check (F02-AC7).
DEFAULT_TEXT = [
    "# Arztbrief\n\nPatient: Hr. Muster-Bauer\n\nDiagnose: Hypertonie\n\n"
    "Medikation: Ramipril 5 mg, Dosierung 1-0-0-0\n\nBefund unauffällig, Entlassung nach Hause."
]


class FakeOcr:
    def __init__(
        self,
        by_sha256: dict[str, list[str]] | None = None,
        default: list[str] | None = None,
        unavailable: bool = False,
    ):
        self.by_sha256 = by_sha256 or {}
        self.default = default if default is not None else DEFAULT_TEXT
        self.unavailable = unavailable
        self.calls = 0

    async def extract(self, data: bytes, mime: str) -> OcrResult:
        self.calls += 1
        if self.unavailable:
            raise OcrUnavailable("fake outage")
        texts = self.by_sha256.get(hashlib.sha256(data).hexdigest(), self.default)
        return OcrResult(pages=[Page(number=i, markdown=t) for i, t in enumerate(texts, start=1)])
