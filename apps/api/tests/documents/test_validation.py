"""F02-AC4: files are checked by content (not by name), size and page count before OCR."""

import io

import pytest
from pypdf import PdfWriter

from app.documents.validation import MAX_BYTES, InvalidFile, validate_upload

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def pdf(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("data", "mime", "pages"),
    [(JPEG, "image/jpeg", 1), (PNG, "image/png", 1), (pdf(1), "application/pdf", 1)],
)
def test_jpeg_png_and_pdf_are_accepted(data, mime, pages):
    checked = validate_upload(data)
    assert (checked.mime, checked.pages, checked.size_bytes) == (mime, pages, len(data))


def test_five_pages_are_the_maximum():
    assert validate_upload(pdf(5)).pages == 5


def test_a_pdf_with_six_pages_is_rejected():
    with pytest.raises(InvalidFile) as error:
        validate_upload(pdf(6))
    assert (error.value.error_code, error.value.status) == ("too_many_pages", 422)
    assert "5 Seiten" in error.value.message


@pytest.mark.parametrize(
    "data",
    [b"GIF89a" + b"\x00" * 50, b"Hallo, ich bin eine Textdatei", b"MZ\x90\x00" + b"\x00" * 50],
    ids=["gif", "text", "exe"],
)
def test_other_content_is_rejected_whatever_the_name(data):
    # The file name is not even passed: only the content decides.
    with pytest.raises(InvalidFile) as error:
        validate_upload(data)
    assert (error.value.error_code, error.value.status) == ("unsupported_type", 415)
    assert "JPEG, PNG oder PDF" in error.value.message


def test_more_than_4_mb_is_rejected():
    with pytest.raises(InvalidFile) as error:
        validate_upload(JPEG + b"\x00" * (MAX_BYTES - len(JPEG) + 1))
    assert (error.value.error_code, error.value.status) == ("file_too_large", 413)
    assert "4 MB" in error.value.message


def test_exactly_4_mb_is_accepted():
    assert validate_upload(JPEG + b"\x00" * (MAX_BYTES - len(JPEG))).size_bytes == MAX_BYTES


@pytest.mark.parametrize("data", [b"%PDF-1.7\n kaputt", b""], ids=["broken-pdf", "empty"])
def test_broken_or_empty_files_are_rejected(data):
    with pytest.raises(InvalidFile) as error:
        validate_upload(data)
    assert error.value.status in (415, 422)


def test_a_pdf_without_pages_is_rejected():
    with pytest.raises(InvalidFile) as error:
        validate_upload(pdf(0))
    assert error.value.status == 422
