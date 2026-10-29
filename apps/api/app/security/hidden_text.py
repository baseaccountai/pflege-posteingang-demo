"""Layer 1a of the prompt-injection protection: text a person cannot see (F07-AC2).

A PDF can carry text that software reads but a person never sees on paper or screen:
white letters on white paper, or letters a few hundredths of a millimetre high. An attacker
puts instructions for the AI there ("Ignoriere alle Regeln ..."), while the nurse who checks
the letter sees nothing unusual.

pypdf walks through the drawing instructions of every page. For each piece of text we know
the font size and the two matrices that scale it (text matrix and page transformation); the
fill colour we follow ourselves through the colour operators and the save/restore stack:

- white: fill colour with every channel at 95 % brightness or more (Gray, RGB or CMYK)
- tiny: effective size below 3 pt

Text in render mode 3 (invisible on purpose) is the OCR layer of scanned PDFs; it is checked
by the other layers like normal text and not reported here. Not covered (F07 spec): text
hidden by clipping, covered by images, placed outside the page, or in special colour spaces.
"""

import io
import logging
import math
import re
from dataclasses import dataclass

from pypdf import PdfReader

log = logging.getLogger(__name__)

MIN_VISIBLE_PT = 3.0
WHITE = 0.95


@dataclass(frozen=True)
class HiddenText:
    page: int  # 1-based
    text: str


@dataclass
class _State:
    fill_white: bool = False
    render_mode: int = 0


class _PageScan:
    """Follows one page's drawing instructions and collects the hidden pieces of text."""

    def __init__(self) -> None:
        self.state = _State()
        self.stack: list[_State] = []
        self.pieces: list[str] = []

    def before(self, operator: bytes, operands: list, cm, tm) -> None:
        op = operator.decode("latin-1")
        if op == "q":  # save the graphics state ...
            self.stack.append(_State(self.state.fill_white, self.state.render_mode))
        elif op == "Q" and self.stack:  # ... and restore it
            self.state = self.stack.pop()
        elif op == "Tr" and operands:
            self.state.render_mode = int(operands[0])
        elif (white := _is_white(op, operands)) is not None:
            self.state.fill_white = white

    def text(self, content: str, cm, tm, font, font_size) -> None:
        if not content.strip() or self.state.render_mode == 3:
            return
        size = float(font_size or 0) * _scale(tm) * _scale(cm)
        if self.state.fill_white or size < MIN_VISIBLE_PT:
            self.pieces.append(content)


def _is_white(operator: str, operands: list) -> bool | None:
    """True/False for a fill colour operator, None for every other operator."""
    values = [float(v) for v in operands if isinstance(v, (int, float))]
    if operator == "g" and len(values) == 1:
        return values[0] >= WHITE
    if operator == "rg" and len(values) == 3:
        return min(values) >= WHITE
    if operator == "k" and len(values) == 4:  # CMYK: no ink at all is white
        return max(values) <= 1 - WHITE
    return None


def _scale(matrix) -> float:
    a, b, c, d = (float(x) for x in matrix[:4])
    return math.sqrt(abs(a * d - b * c))


def find_hidden_text(pdf: bytes) -> list[HiddenText]:
    try:
        reader = PdfReader(io.BytesIO(pdf))
        pages = list(reader.pages)
    except Exception:  # not a PDF (a photo) or broken: nothing to find here
        return []

    found = []
    for number, page in enumerate(pages, start=1):
        scan = _PageScan()
        try:
            page.extract_text(visitor_operand_before=scan.before, visitor_text=scan.text)
        except Exception:
            log.warning("hidden text check could not read page %s", number)
            continue
        hidden = re.sub(r"\s+", " ", " ".join(scan.pieces)).strip()
        if len(hidden) >= 3:
            found.append(HiddenText(number, hidden))
    return found
