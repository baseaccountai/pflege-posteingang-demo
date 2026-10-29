"""F07-AC2: text in a PDF that a person cannot see (white or tiny) is found."""

import io

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from app.security.hidden_text import find_hidden_text
from samples import generate


def pdf(draw) -> bytes:
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4, invariant=1)
    canvas.setFont("Helvetica", 11)
    canvas.drawString(60, 760, "Entlassungsbrief, sichtbarer Text")
    draw(canvas)
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def test_the_prepared_letter_reveals_its_hidden_instruction():
    found = find_hidden_text(generate.pdf_bytes(generate.ANGRIFF_VERSTECKT, generate.HIDDEN_ATTACK))
    assert len(found) == 1
    assert found[0].page == 1
    assert generate.HIDDEN_ATTACK in found[0].text


@pytest.mark.parametrize(
    "lines", [generate.ARZTBRIEF, generate.MEDIKATIONSPLAN, generate.ANGRIFF_HINWEIS]
)
def test_ordinary_letters_have_no_hidden_text(lines):
    # The red, transparent MUSTER watermark is visible and does not count.
    assert find_hidden_text(generate.pdf_bytes(lines)) == []


def white_rgb(c):
    c.setFillColorRGB(1, 1, 1)
    c.drawString(60, 700, "Weiße Schrift in RGB")


def white_gray(c):
    c.setFillGray(0.97)
    c.drawString(60, 700, "Fast weiße Schrift in Grau")


def white_cmyk(c):
    c.setFillColorCMYK(0, 0, 0, 0)
    c.drawString(60, 700, "Weiße Schrift in CMYK")


def tiny_black(c):
    c.setFont("Helvetica", 2)
    c.drawString(60, 700, "Winzige schwarze Schrift")


def scaled_down(c):
    c.saveState()
    c.scale(0.1, 0.1)  # 11 pt drawn at a tenth: 1.1 pt on paper
    c.drawString(600, 7000, "Herunterskalierte Schrift")
    c.restoreState()


@pytest.mark.parametrize(
    "draw", [white_rgb, white_gray, white_cmyk, tiny_black, scaled_down], ids=lambda f: f.__name__
)
def test_white_or_tiny_text_is_found(draw):
    found = find_hidden_text(pdf(draw))
    assert len(found) == 1 and "Schrift" in found[0].text
    assert "sichtbarer Text" not in found[0].text


def test_colour_returns_after_restore_state():
    def draw(c):
        c.saveState()
        c.setFillColorRGB(1, 1, 1)
        c.restoreState()
        c.drawString(60, 700, "Wieder schwarze Schrift")

    assert find_hidden_text(pdf(draw)) == []


def test_invisible_ocr_layer_of_a_scan_is_not_counted():
    # Render mode 3 is how scanners put their OCR text under the image; it is checked like
    # normal text by the other layers, not reported as hidden.
    def draw(c):
        c.setFillColorRGB(1, 1, 1)  # scanners may use any colour and size for this layer
        text = c.beginText(60, 700)
        text.setFont("Helvetica", 1)
        text.setTextRenderMode(3)
        text.textLine("Text der OCR-Ebene eines Scans")
        c.drawText(text)

    assert find_hidden_text(pdf(draw)) == []


def test_something_that_is_no_pdf_gives_no_findings():
    assert find_hidden_text(b"\xff\xd8\xff\xe0 jpeg") == []
