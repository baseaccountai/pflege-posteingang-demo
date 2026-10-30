"""OCR interface (F02): file in, Markdown per page out. Providers are exchangeable."""

from dataclasses import dataclass, field
from typing import Protocol


class OcrUnavailable(Exception):
    """Provider not reachable, timed out or answered with an error -> failed/ocr_unavailable."""


@dataclass(frozen=True)
class Page:
    number: int  # 1-based
    markdown: str


@dataclass(frozen=True)
class OcrResult:
    pages: list[Page] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(page.markdown for page in self.pages)


class OcrProvider(Protocol):
    model_name: str  # named in the audit log (F12-AC2)

    async def extract(self, data: bytes, mime: str) -> OcrResult: ...
