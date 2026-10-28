"""Structure-aware chunking of OCR Markdown (F05-AC2, AC3).

A chunk is the piece of a document that is embedded and later shown as a source. The rules:

1. Structure first: a new section starts at every heading `#` to `###`. A section up to the
   target size (600 tokens) is one chunk - a heading and its text belong together.
2. Tables stay whole as long as they fit into the maximum (800 tokens): a medication plan
   split in the middle would answer "which dose?" with half a table.
3. Only a section above the target is split, step by step as coarse as possible:
   paragraph -> line -> sentence -> (only for endless words) characters. Consecutive parts
   overlap by about 12 %, so a sentence at a border is found from both sides.
4. A table above the maximum is split by rows; every part repeats the header row, so each
   part can still be read on its own (AC3).

Every part of a section starts with the section's heading line, so a chunk says what it is
about. A section that goes on on the next page keeps its heading (the OCR gives one Markdown
text per page; the page number is the source shown to the user).

Tokens are estimated as characters / 4 - good enough for sizes, and replaceable (`count`).
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass

TARGET_TOKENS = 600
MAX_TOKENS = 800
OVERLAP_SHARE = 0.12
OVERLAP_TOKENS = int(TARGET_TOKENS * OVERLAP_SHARE)  # 72

HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

Count = Callable[[str], int]


def count_tokens(text: str) -> int:
    """Rough token estimate: about 4 characters per token."""
    return math.ceil(len(text) / 4)


@dataclass(frozen=True)
class Chunk:
    page: int
    heading: str | None
    content: str


@dataclass(frozen=True)
class _Section:
    page: int
    heading: str | None
    heading_line: str | None  # None if the section started on an earlier page
    body: str


def split_pages(
    pages: list[tuple[int, str]],
    count: Count = count_tokens,
    target: int = TARGET_TOKENS,
    maximum: int = MAX_TOKENS,
) -> list[Chunk]:
    """Chunks of all pages, in reading order. `pages` = [(page number, Markdown), ...]."""
    splitter = _Splitter(count, target, maximum)
    chunks: list[Chunk] = []
    for section in _sections(pages):
        chunks += splitter.section(section)
    return chunks


def _sections(pages: list[tuple[int, str]]) -> list[_Section]:
    """Cuts the pages at headings; text before the first heading of a page belongs to the
    section of the previous page."""
    sections: list[_Section] = []
    heading: str | None = None
    for page, markdown in pages:
        heading_line: str | None = None  # a new page: the heading is not repeated on it
        lines: list[str] = []
        for line in [*markdown.splitlines(), None]:  # None: end of the page
            match = HEADING.match(line.strip()) if line is not None else None
            if line is not None and not match:
                lines.append(line)
                continue
            body = "\n".join(lines).strip()
            if body:
                sections.append(_Section(page, heading, heading_line, body))
            if match:
                heading, heading_line, lines = match.group(2), line.strip(), []
    return sections


def _is_table_line(line: str) -> bool:
    return line.lstrip().startswith("|")


def _blocks(body: str) -> list[tuple[str, str]]:
    """Paragraphs and tables of a section body as ("text" | "table", content). A table is a
    run of lines starting with "|", also without blank lines around it."""
    blocks: list[tuple[str, str]] = []
    for paragraph in re.split(r"\n\s*\n", body):
        run: list[str] = []
        run_is_table = False
        for line in paragraph.splitlines():
            if run and _is_table_line(line) != run_is_table:
                blocks.append(("table" if run_is_table else "text", "\n".join(run)))
                run = []
            run_is_table = _is_table_line(line)
            run.append(line)
        if run:
            blocks.append(("table" if run_is_table else "text", "\n".join(run)))
    return [(kind, text.strip()) for kind, text in blocks if text.strip()]


class _Splitter:
    def __init__(self, count: Count, target: int, maximum: int):
        self.count, self.target, self.maximum = count, target, maximum
        self.overlap = int(target * OVERLAP_SHARE)

    def section(self, section: _Section) -> list[Chunk]:
        prefix = f"{section.heading_line}\n" if section.heading_line else ""
        whole = prefix + section.body
        if self.count(whole) <= self.target:  # rule 1: small sections stay whole
            return [Chunk(section.page, section.heading, whole)]

        parts: list[str] = []
        text_budget = self.target - self.count(prefix)
        pending: list[str] = []  # text pieces waiting to fill the current part
        for kind, block in _blocks(section.body):
            if kind == "table":
                parts += self._flush(pending)
                pending = []
                parts += self._table(block, self.maximum - self.count(prefix))
            else:
                pending += self._pieces(block, text_budget)
        parts += self._flush(pending, text_budget)
        return [Chunk(section.page, section.heading, prefix + part) for part in parts]

    # --- text: paragraph -> line -> sentence -> characters ------------------------------
    def _pieces(self, text: str, budget: int) -> list[str]:
        """The text in pieces of at most `budget` tokens, as coarse as possible (rule 3)."""
        if self.count(text) <= budget:
            return [text]
        for separator in ("\n", SENTENCE_END):
            parts = text.split(separator) if isinstance(separator, str) else separator.split(text)
            if len(parts) > 1:
                return [piece for part in parts for piece in self._pieces(part, budget)]
        return self._hard_cut(text, budget)

    def _hard_cut(self, text: str, budget: int) -> list[str]:
        """Last resort for a "word" longer than the budget: cut by characters."""
        pieces = []
        while text:
            size = len(text)
            while self.count(text[:size]) > budget:
                size = max(1, size * budget // self.count(text[:size]) - 1)
            pieces.append(text[:size])
            text = text[size:]
        return pieces

    def _flush(self, pieces: list[str], budget: int | None = None) -> list[str]:
        """Packs pieces into parts of up to `budget` tokens; every part after the first starts
        with the end of the previous one (overlap)."""
        budget = budget if budget is not None else self.target
        parts: list[str] = []
        current = ""
        for piece in pieces:
            candidate = f"{current}\n{piece}" if current else piece
            if not current or self.count(candidate) <= budget:
                current = candidate
                continue
            parts.append(current)
            tail = self._tail(current)
            current = f"{tail}\n{piece}" if tail else piece
        if current:
            parts.append(current)
        return parts

    def _tail(self, text: str) -> str:
        """The last words of `text` that fit into the overlap."""
        words = text.split(" ")
        taken: list[str] = []
        for word in reversed(words):
            if self.count(" ".join([word, *taken])) > self.overlap:
                break
            taken.insert(0, word)
        return " ".join(taken)

    # --- tables: whole, or by rows with the header in every part (rule 2, rule 4) --------
    def _table(self, table: str, budget: int) -> list[str]:
        if self.count(table) <= budget:
            return [table]
        lines = table.splitlines()
        has_separator = len(lines) > 1 and set(lines[1].replace("|", "").strip()) <= set("-: ")
        header = "\n".join(lines[:2] if has_separator else lines[:1])
        rows = lines[2:] if has_separator else lines[1:]
        parts: list[str] = []
        current: list[str] = []
        for row in rows:
            if current and self.count("\n".join([header, *current, row])) > budget:
                parts.append("\n".join([header, *current]))
                current = []
            current.append(row)
        if current:
            parts.append("\n".join([header, *current]))
        return parts
