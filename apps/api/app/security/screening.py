"""The injection check of a document before any model reads it (F07-AC1, AC2, AC5).

    OCR pages ──▶ sections (headings, paragraphs, tables, lists)
              ──▶ layer 1a: text a person cannot see in the PDF (hidden_text.py)
              ──▶ layer 1b: rules (patterns/*.toml)
              ──▶ layer 2:  checker model, sections bundled into calls of at most
                            20 000 characters, each call booked (guard_document quota)
              ──▶ findings + cleaned pages: every suspicious section replaced by EXCLUDED

The cleaned pages are the only text the field suggestion and the indexing get. A finding
costs the nurse one paragraph, not the whole letter; she still sees the original and
decides. If the checker cannot run, the error is passed on - nothing goes on unchecked.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.privacy.gateway import ModelGateway
from app.security.classifier import DOCUMENT_MAX_CHARS, classify_document
from app.security.hidden_text import find_hidden_text
from app.security.patterns import matching_rules
from app.security.sections import split_sections

EXCLUDED = "[Abschnitt entfernt: verdächtig]"
HIDDEN_EXPLANATION = (
    "Text in weißer oder winziger Schrift: für Menschen unsichtbar, für Software lesbar."
    " Er wird nicht verarbeitet."
)
CLASSIFIER_EXPLANATION = "Das Prüfmodell hält diesen Abschnitt für eine Anweisung an die KI."
MAX_EXCERPT = 500


@dataclass(frozen=True)
class Finding:
    page: int
    start: int | None  # offsets in the page's markdown; None: not in the OCR text
    end: int | None
    layer: str  # hidden_text | pattern | classifier
    rule_id: str
    category: str
    excerpt: str
    explanation: str


@dataclass(frozen=True)
class Screening:
    result: str  # clean | suspicious
    screened_pages: list[dict]
    findings: list[Finding]


@dataclass(frozen=True)
class _Part:
    page: int
    start: int
    end: int
    text: str


def _words(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


class Screener:
    def __init__(self, gateway: ModelGateway, book_guard: Callable[[object], Awaitable[None]]):
        self.gateway = gateway
        self.book_guard = book_guard  # books one guard_document call (raises QuotaExceeded)

    @property
    def model_name(self) -> str:
        return self.gateway.guard_model

    async def __call__(self, principal, pages: list[dict], pdf: bytes | None) -> Screening:
        parts = [
            _Part(page["page"], s.start, s.end, page["markdown"][s.start : s.end])
            for page in pages
            for s in split_sections(page["markdown"])
        ]
        findings: list[Finding] = []
        suspicious: set[int] = set()

        # Layer 1a: text nobody can see. Cut it out where the OCR has read it, too.
        for hidden in find_hidden_text(pdf) if pdf else []:
            probe = _words(hidden.text)[:40]
            located = [
                i for i, p in enumerate(parts) if p.page == hidden.page and probe in _words(p.text)
            ]
            suspicious.update(located)
            where = parts[located[0]] if located else None
            findings.append(
                Finding(
                    page=hidden.page,
                    start=where.start if where else None,
                    end=where.end if where else None,
                    layer="hidden_text",
                    rule_id="hidden-text",
                    category="hidden_instruction",
                    excerpt=hidden.text[:MAX_EXCERPT],
                    explanation=HIDDEN_EXPLANATION,
                )
            )

        # Layer 1b: rules.
        for i, part in enumerate(parts):
            for rule in matching_rules(part.text):
                suspicious.add(i)
                findings.append(
                    self._finding(part, "pattern", rule.id, rule.category, rule.explanation)
                )

        # Layer 2: the checker model, in bundles of at most DOCUMENT_MAX_CHARS. A section
        # longer than that is checked in pieces; one suspicious piece excludes the section.
        flagged: dict[int, object] = {}
        for bundle in self._bundles(parts):
            await self.book_guard(principal)
            verdicts = await classify_document(self.gateway, [text for _, text in bundle])
            for (i, _), verdict in zip(bundle, verdicts, strict=True):
                if verdict.injection and i not in flagged:
                    flagged[i] = verdict
        for i, verdict in sorted(flagged.items()):
            suspicious.add(i)
            findings.append(
                self._finding(
                    parts[i],
                    "classifier",
                    "classifier",
                    verdict.category or "injection",
                    verdict.reason or CLASSIFIER_EXPLANATION,
                )
            )

        return Screening(
            result="suspicious" if findings else "clean",
            screened_pages=self._cleaned(pages, [parts[i] for i in sorted(suspicious)]),
            findings=findings,
        )

    @staticmethod
    def _finding(part: _Part, layer: str, rule_id: str, category: str, explanation: str) -> Finding:
        return Finding(
            part.page,
            part.start,
            part.end,
            layer,
            rule_id,
            category,
            part.text[:MAX_EXCERPT],
            explanation,
        )

    @staticmethod
    def _bundles(parts: list[_Part]) -> list[list[tuple[int, str]]]:
        """(part index, text) pieces, consecutive ones together up to DOCUMENT_MAX_CHARS per
        call. A part longer than that becomes several pieces, so it is checked to its end."""
        pieces = [
            (i, part.text[start : start + DOCUMENT_MAX_CHARS])
            for i, part in enumerate(parts)
            for start in range(0, max(len(part.text), 1), DOCUMENT_MAX_CHARS)
        ]
        bundles, current, size = [], [], 0
        for i, text in pieces:
            if current and size + len(text) > DOCUMENT_MAX_CHARS:
                bundles.append(current)
                current, size = [], 0
            current.append((i, text))
            size += len(text)
        if current:
            bundles.append(current)
        return bundles

    @staticmethod
    def _cleaned(pages: list[dict], cut: list[_Part]) -> list[dict]:
        cleaned = []
        for page in pages:
            markdown = page["markdown"]
            for part in sorted((p for p in cut if p.page == page["page"]), key=lambda p: -p.start):
                markdown = markdown[: part.start] + EXCLUDED + markdown[part.end :]
            cleaned.append({**page, "markdown": markdown})
        return cleaned
