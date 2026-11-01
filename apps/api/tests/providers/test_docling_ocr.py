"""F11-AC17: Docling (local OCR) against a stand-in of docling-serve (respx).

The good answer is a real one of docling-serve v1.37.0 for samples/arztbrief_muster-bauer.pdf
(fixtures/, trimmed to the fields we read). Pages come back as Markdown like Mistral OCR's;
every failure becomes OcrUnavailable, so the upload ends as "OCR nicht verfügbar" with retry.
"""

import json
from pathlib import Path

import httpx
import pytest
import respx

from app.providers.ocr.base import OcrUnavailable, Page
from app.providers.ocr.docling import PAGE_BREAK, DoclingOcr

pytestmark = pytest.mark.anyio

BASE = "http://localhost:5001"
URL = f"{BASE}/v1/convert/file"
RECORDED = json.loads(
    (Path(__file__).parent / "fixtures" / "docling_arztbrief_muster-bauer.json").read_text()
)
PDF = b"%PDF-1.7 test"
JPEG = b"\xff\xd8\xff test"


def answer(markdown: str, status: str = "success") -> dict:
    return {"document": {"filename": "f", "md_content": markdown}, "status": status, "errors": []}


@respx.mock
async def test_the_recorded_letter_comes_back_as_one_page_of_markdown():
    respx.post(URL).mock(return_value=httpx.Response(200, json=RECORDED))
    result = await DoclingOcr(BASE).extract(PDF, "application/pdf")
    (page,) = result.pages
    assert page.number == 1
    assert page.markdown.startswith("## Entlassungsbrief")
    assert "Ramipril 5 mg 1-0-0-0" in page.markdown


@respx.mock
async def test_pages_are_split_at_the_page_break_placeholder():
    respx.post(URL).mock(
        return_value=httpx.Response(200, json=answer(f"# Seite 1\n\n{PAGE_BREAK}\n\n# Seite 2\n"))
    )
    result = await DoclingOcr(BASE).extract(PDF, "application/pdf")
    assert result.pages == [Page(1, "# Seite 1"), Page(2, "# Seite 2")]


@respx.mock
@pytest.mark.parametrize(
    ("data", "mime", "name"),
    [(PDF, "application/pdf", "dokument.pdf"), (JPEG, "image/jpeg", "dokument.jpg")],
)
async def test_the_file_is_sent_as_upload_asking_for_markdown_with_page_breaks(data, mime, name):
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=answer("x")))
    await DoclingOcr(BASE).extract(data, mime)
    body = route.calls.last.request.content
    assert f'filename="{name}"'.encode() in body and data in body
    assert b'name="to_formats"\r\n\r\nmd' in body
    assert PAGE_BREAK.encode() in body
    assert b'name="ocr_lang"\r\n\r\nde' in body


@respx.mock
@pytest.mark.parametrize(
    "reply",
    [
        httpx.Response(500),
        httpx.Response(422, json={"detail": "bad"}),
        httpx.Response(200, text="kein json"),
        httpx.Response(200, json={"unexpected": True}),
        httpx.Response(200, json=answer("", status="failure")),
        httpx.Response(200, json=answer("teils", status="partial_success")),
    ],
    ids=["500", "422", "not-json", "wrong-shape", "failure", "partial"],
)
async def test_errors_become_ocr_unavailable(reply):
    respx.post(URL).mock(return_value=reply)
    with pytest.raises(OcrUnavailable):
        await DoclingOcr(BASE).extract(PDF, "application/pdf")


@respx.mock
@pytest.mark.parametrize("error", [httpx.ReadTimeout("slow"), httpx.ConnectError("down")])
async def test_a_timeout_or_a_stopped_service_becomes_ocr_unavailable(error):
    respx.post(URL).mock(side_effect=error)
    with pytest.raises(OcrUnavailable):
        await DoclingOcr(BASE).extract(PDF, "application/pdf")


def test_the_timeout_leaves_time_for_a_photo_on_a_laptop_cpu():
    # Measured 01.11.2026 on the applicant's laptop (no GPU): PDF 14 s, phone photo 32 s.
    assert DoclingOcr(BASE).timeout == 180
