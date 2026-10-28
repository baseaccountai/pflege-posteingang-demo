"""Real, tiny images for upload tests - signature bytes alone are not a valid image."""

import io

from PIL import Image


def image_bytes(fmt: str) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format=fmt)
    return buffer.getvalue()


JPEG = image_bytes("JPEG")
PNG = image_bytes("PNG")
