"""Upload checks before anything else happens (F02-AC4).

The type is decided by the first bytes of the file ("magic bytes"), never by the file name
or the Content-Type header the browser sends - both can be set to anything. Only files that
pass here are stored, delivered back and sent to OCR.
"""

import io
from dataclasses import dataclass

from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PyPdfError

# Vercel accepts at most 4.5 MB per request; 4 MB leaves room for the multipart wrapping.
MAX_BYTES = 4 * 1024 * 1024
MAX_PDF_PAGES = 5
# A photo of a care document needs far less; more pixels only cost memory when decoding
# (a small PNG can unpack to gigabytes).
MAX_IMAGE_PIXELS = 40_000_000

MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"%PDF": "application/pdf",
}


class InvalidFile(Exception):
    """Rejected upload: error_code for the app, German message for the user, HTTP status."""

    def __init__(self, error_code: str, message: str, status: int):
        super().__init__(error_code)
        self.error_code = error_code
        self.message = message
        self.status = status


@dataclass(frozen=True)
class CheckedFile:
    mime: str
    size_bytes: int
    pages: int


def detect_mime(data: bytes) -> str | None:
    return next((mime for magic, mime in MAGIC.items() if data.startswith(magic)), None)


def count_pdf_pages(data: bytes) -> int:
    try:
        pages = len(PdfReader(io.BytesIO(data)).pages)
    except (PyPdfError, ValueError, OSError) as error:
        raise InvalidFile(
            "unreadable_pdf", "Das PDF ist beschädigt und kann nicht gelesen werden.", 422
        ) from error
    if pages == 0:
        raise InvalidFile("unreadable_pdf", "Das PDF enthält keine Seiten.", 422)
    return pages


UNREADABLE_IMAGE = (
    "unreadable_image",
    "Das Bild ist beschädigt und kann nicht gelesen werden.",
    422,
)


def check_image(data: bytes) -> None:
    """The signature alone proves nothing: the image must decode completely (Codex review
    Phase 3 #6), and the size is checked from the header before decoding."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise InvalidFile(*UNREADABLE_IMAGE)
            image.load()
    except InvalidFile:
        raise
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
        raise InvalidFile(*UNREADABLE_IMAGE) from error


def validate_upload(data: bytes) -> CheckedFile:
    if len(data) > MAX_BYTES:
        raise InvalidFile("file_too_large", "Die Datei ist größer als 4 MB.", 413)
    mime = detect_mime(data)
    if mime is None:
        raise InvalidFile("unsupported_type", "Nur JPEG, PNG oder PDF sind erlaubt.", 415)
    if mime != "application/pdf":
        check_image(data)
    # A photo is always one page; for a PDF the page count costs OCR money, so it is capped.
    pages = count_pdf_pages(data) if mime == "application/pdf" else 1
    if pages > MAX_PDF_PAGES:
        raise InvalidFile(
            "too_many_pages", f"Das PDF hat {pages} Seiten, erlaubt sind höchstens 5 Seiten.", 422
        )
    return CheckedFile(mime=mime, size_bytes=len(data), pages=pages)
