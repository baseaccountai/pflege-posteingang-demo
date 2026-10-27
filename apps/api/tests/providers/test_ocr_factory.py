"""F02-AC11: the OCR provider is chosen by configuration only."""

import hashlib

import pytest

from app.config import Settings
from app.providers.ocr import Page, create_ocr_provider
from app.providers.ocr.base import OcrUnavailable
from app.providers.ocr.docling import DoclingOcr
from app.providers.ocr.fake import FakeOcr

pytestmark = pytest.mark.anyio


def test_docling_is_used_when_configured():
    provider = create_ocr_provider(Settings(ocr_provider="docling"))
    assert isinstance(provider, DoclingOcr)


async def test_docling_is_not_connected_in_stage_1():
    # Interface only until phase 8: a clear "unavailable", never a silent empty result.
    with pytest.raises(OcrUnavailable):
        await DoclingOcr("http://docling:5001").extract(b"%PDF", "application/pdf")


def test_fake_is_used_when_configured():
    assert isinstance(create_ocr_provider(Settings(ocr_provider="fake")), FakeOcr)


def test_unknown_provider_is_a_configuration_error():
    with pytest.raises(ValueError):
        Settings(ocr_provider="tesseract")


async def test_fake_returns_the_text_registered_for_a_file():
    data = b"\xff\xd8\xff arztbrief"
    fake = FakeOcr({hashlib.sha256(data).hexdigest(): ["# Arztbrief", "Seite 2"]})
    result = await fake.extract(data, "image/jpeg")
    assert result.pages == [
        Page(number=1, markdown="# Arztbrief"),
        Page(number=2, markdown="Seite 2"),
    ]


async def test_fake_answers_unknown_files_with_its_default_text():
    result = await FakeOcr(default=["Standardtext"]).extract(b"x", "image/png")
    assert [page.markdown for page in result.pages] == ["Standardtext"]


async def test_fake_can_simulate_an_outage():
    with pytest.raises(OcrUnavailable):
        await FakeOcr(unavailable=True).extract(b"x", "image/png")
