"""F02-AC11: the OCR provider is chosen by configuration only."""

import hashlib
import io
from pathlib import Path

import pytest
from PIL import Image

from app.config import Settings
from app.providers.ocr import Page, create_ocr_provider
from app.providers.ocr.base import OcrUnavailable
from app.providers.ocr.docling import DoclingOcr
from app.providers.ocr.fake import FakeOcr

pytestmark = pytest.mark.anyio


def test_docling_is_used_when_configured():
    provider = create_ocr_provider(Settings(ocr_provider="docling"))
    assert isinstance(provider, DoclingOcr)


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


SAMPLES = Path(__file__).resolve().parents[4] / "samples"


def browser_reencoded(path: Path) -> bytes:
    """What the browser uploads: scaled to at most 2000 px and saved again as JPEG 0.85."""
    with Image.open(path) as image:
        image.thumbnail((2000, 2000))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, "JPEG", quality=85)
        return buffer.getvalue()


async def test_fake_from_samples_reads_pdfs_by_content():
    fake = FakeOcr.from_samples(SAMPLES)
    result = await fake.extract((SAMPLES / "bad/kochrezept.pdf").read_bytes(), "application/pdf")
    assert result.text == (SAMPLES / "ocr/bad__kochrezept.pdf.md").read_text()


@pytest.mark.parametrize(
    "name",
    [
        "bad/leere_seite.jpg",
        "bad/unscharf.jpg",
        "bad/schief.jpg",
        "arztbrief_muster-bauer_foto.jpg",
    ],
)
async def test_fake_from_samples_recognises_photos_after_browser_downscaling(name):
    fake = FakeOcr.from_samples(SAMPLES)
    result = await fake.extract(browser_reencoded(SAMPLES / name), "image/jpeg")
    expected = (SAMPLES / "ocr" / f"{name.replace('/', '__')}.md").read_text()
    assert result.text == expected


async def test_fake_from_samples_answers_other_images_with_the_default():
    buffer = io.BytesIO()
    Image.new("RGB", (300, 300), (0, 120, 0)).save(buffer, "JPEG")
    result = await FakeOcr.from_samples(SAMPLES).extract(buffer.getvalue(), "image/jpeg")
    assert "Arztbrief" in result.text


def test_fake_provider_loads_the_samples_when_configured():
    provider = create_ocr_provider(Settings(ocr_provider="fake", fake_ocr_samples=str(SAMPLES)))
    assert isinstance(provider, FakeOcr) and provider.by_image
