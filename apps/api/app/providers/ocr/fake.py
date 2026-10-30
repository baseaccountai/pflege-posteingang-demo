"""OCR stand-in for tests and the end-to-end run without a Mistral key (OCR_PROVIDER=fake).

Answers with the Markdown registered for a file (by SHA-256) or with a default text, so a
test can decide what the "OCR" reads. Never used in the public demo.
"""

import hashlib
import io
from pathlib import Path

from app.providers.ocr.base import OcrResult, OcrUnavailable, Page

# Readable care document, long enough for the readability check (F02-AC7).
DEFAULT_TEXT = [
    "# Arztbrief\n\nKlinikum Musterstadt, Innere Medizin, 20.10.2026\n"
    "Patient: Hr. Muster-Bauer\n\n## Diagnosen\n- Hypertonie\n\n"
    "| Medikament | Stärke | Dosierung |\n|---|---|---|\n| Ramipril | 5 mg | 1-0-0-0 |\n\n"
    "Befund unauffällig, Entlassung nach Hause."
]


MAX_EDGE = 2000  # the browser scales photos to this before the upload (F02-AC3)


def image_print(data: bytes) -> tuple[tuple[int, int], int]:
    """Size after the browser's downscaling + 8x8 average hash.

    Both survive scaling and JPEG re-encoding, unlike a SHA-256 of the bytes. Pillow is a
    dev dependency (sample generator), so it is imported only when the fake needs it.
    """
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        scale = min(1, MAX_EDGE / max(image.size))
        size = (round(image.width * scale), round(image.height * scale))
        pixels = list(image.convert("L").resize((8, 8)).get_flattened_data())
    mean = sum(pixels) / len(pixels)
    return size, sum(1 << i for i, value in enumerate(pixels) if value > mean)


class FakeOcr:
    model_name = "fake-ocr"

    def __init__(
        self,
        by_sha256: dict[str, list[str]] | None = None,
        default: list[str] | None = None,
        unavailable: bool = False,
        by_image: list[tuple[tuple[tuple[int, int], int], list[str]]] | None = None,
    ):
        self.by_sha256 = by_sha256 or {}
        self.by_image = by_image or []
        self.default = default if default is not None else DEFAULT_TEXT
        self.unavailable = unavailable
        self.calls = 0

    @classmethod
    def from_samples(cls, folder: Path) -> "FakeOcr":
        """Knows every file in samples/ with the OCR text from samples/ocr/ (F10-AC2)."""
        by_sha256, by_image = {}, []
        for path in sorted(folder.rglob("*")):
            if path.suffix not in {".pdf", ".jpg", ".png"}:
                continue
            name = path.relative_to(folder).as_posix().replace("/", "__")
            text = [(folder / "ocr" / f"{name}.md").read_text(encoding="utf-8")]
            data = path.read_bytes()
            by_sha256[hashlib.sha256(data).hexdigest()] = text
            if path.suffix != ".pdf":
                by_image.append((image_print(data), text))
        return cls(by_sha256=by_sha256, by_image=by_image)

    def _texts(self, data: bytes, mime: str) -> list[str]:
        exact = self.by_sha256.get(hashlib.sha256(data).hexdigest())
        if exact is not None or not mime.startswith("image/") or not self.by_image:
            return exact if exact is not None else self.default
        (width, height), fingerprint = image_print(data)
        # Same size (± rounding) and the closest hash; anything else is "some other photo".
        close = [
            (bin(fingerprint ^ known).count("1"), text)
            for ((w, h), known), text in self.by_image
            if abs(w - width) <= 2 and abs(h - height) <= 2
        ]
        best = min(close, default=None, key=lambda item: item[0])
        return best[1] if best and best[0] <= 10 else self.default

    async def extract(self, data: bytes, mime: str) -> OcrResult:
        self.calls += 1
        if self.unavailable:
            raise OcrUnavailable("fake outage")
        texts = self._texts(data, mime)
        return OcrResult(pages=[Page(number=i, markdown=t) for i, t in enumerate(texts, start=1)])
