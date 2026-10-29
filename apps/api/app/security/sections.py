"""Sections of an OCR page, the unit the injection check looks at (F07-AC5).

A finding excludes only its section, not the whole document: one suspicious paragraph
should not cost the nurse the rest of a letter. A section is a heading, a table, a list,
or a paragraph (lines up to the next blank line, heading, table or list).
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    start: int  # character offsets in the page's markdown
    end: int


def _kind(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return "blank"
    if stripped.startswith("#"):
        return "heading"
    if stripped.startswith("|"):
        return "table"
    if re.match(r"([-*•]|\d+[.)])\s", stripped):
        return "list"
    return "text"


def split_sections(markdown: str) -> list[Section]:
    sections: list[Section] = []
    current: tuple[str, int, int] | None = None  # (kind, start, end)
    offset = 0
    for line in markdown.splitlines(keepends=True):
        kind, start, end = _kind(line), offset, offset + len(line.rstrip("\r\n"))
        offset += len(line)
        if current and (kind != current[0] or kind in ("blank", "heading")):
            if current[0] != "blank":
                sections.append(Section(current[1], current[2]))
            current = None
        if current is None:
            current = (kind, start, end)
        else:
            current = (kind, current[1], end)
    if current and current[0] != "blank":
        sections.append(Section(current[1], current[2]))
    return sections
