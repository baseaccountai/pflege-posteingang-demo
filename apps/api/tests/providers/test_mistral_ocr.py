"""F02-AC6, F02-AC8: Mistral OCR adapter against a stand-in of the Mistral API (respx)."""

import base64
import json

import httpx
import pytest
import respx

from app.config import Settings
from app.providers.ocr import Page, create_ocr_provider
from app.providers.ocr.base import OcrUnavailable
from app.providers.ocr.mistral import OCR_URL, MistralOcr

pytestmark = pytest.mark.anyio

KEY = "test-key-not-real"
PDF = b"%PDF-1.7 test"
JPEG = b"\xff\xd8\xff test"


def ocr_answer(*pages: tuple[int, str]) -> dict:
    return {
        "pages": [
            {"index": i, "markdown": md, "images": [], "dimensions": None} for i, md in pages
        ],
        "model": "mistral-ocr-2503-completion",
        "usage_info": {"pages_processed": len(pages), "doc_size_bytes": None},
    }


@respx.mock
async def test_pdf_is_sent_as_data_url_and_pages_come_back_in_order():
    route = respx.post(OCR_URL).mock(
        return_value=httpx.Response(200, json=ocr_answer((1, "Seite zwei"), (0, "Seite eins")))
    )
    result = await MistralOcr(KEY, "mistral-ocr-latest").extract(PDF, "application/pdf")

    assert result.pages == [Page(1, "Seite eins"), Page(2, "Seite zwei")]
    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    assert body["model"] == "mistral-ocr-latest"
    assert body["document"] == {
        "type": "document_url",
        "document_url": "data:application/pdf;base64," + base64.b64encode(PDF).decode(),
    }
    assert body.get("include_image_base64") is False  # no images back: smaller, cheaper


@respx.mock
async def test_a_photo_is_sent_as_image_url():
    route = respx.post(OCR_URL).mock(return_value=httpx.Response(200, json=ocr_answer((0, "x"))))
    await MistralOcr(KEY, "mistral-ocr-latest").extract(JPEG, "image/jpeg")
    document = json.loads(route.calls.last.request.content)["document"]
    assert document == {
        "type": "image_url",
        "image_url": "data:image/jpeg;base64," + base64.b64encode(JPEG).decode(),
    }


@respx.mock
@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(429),
        httpx.Response(401),
        httpx.Response(200, text="kein json"),
        httpx.Response(200, json={"unexpected": True}),
    ],
    ids=["500", "503", "rate-limit", "bad-key", "not-json", "wrong-shape"],
)
async def test_errors_become_ocr_unavailable_without_leaking_the_key(answer):
    respx.post(OCR_URL).mock(return_value=answer)
    with pytest.raises(OcrUnavailable) as error:
        await MistralOcr(KEY, "mistral-ocr-latest").extract(PDF, "application/pdf")
    assert KEY not in str(error.value)


@respx.mock
async def test_a_timeout_becomes_ocr_unavailable():
    respx.post(OCR_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(OcrUnavailable):
        await MistralOcr(KEY, "mistral-ocr-latest").extract(PDF, "application/pdf")


@respx.mock
async def test_without_a_key_nothing_is_sent():
    route = respx.post(OCR_URL)
    with pytest.raises(OcrUnavailable):
        await MistralOcr("", "mistral-ocr-latest").extract(PDF, "application/pdf")
    assert not route.called


def test_mistral_is_the_default_provider():
    provider = create_ocr_provider(Settings(mistral_api_key=KEY, mistral_ocr_model="ocr-x"))
    assert isinstance(provider, MistralOcr)
    assert provider.model == "ocr-x"
    assert provider.timeout == 60
