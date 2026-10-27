"""Real test against Mistral with the sample documents (F02/F03 "Realtest").

Run by the developer in their own terminal, never in CI:

    cd apps/api && uv run python -m scripts.mistral_probe ../../.env

Reads MISTRAL_API_KEY from the given .env file and prints only results, never the key.
Sends only invented sample documents from samples/. Costs: 3 OCR pages + up to 6 chat calls.
"""

import asyncio
import sys
from pathlib import Path

from app.extraction.service import Extractor
from app.providers.llm.base import LlmUnavailable
from app.providers.llm.mistral import MistralLlm
from app.providers.ocr.base import OcrUnavailable
from app.providers.ocr.mistral import MistralOcr
from scripts.provision_db_roles import read_env

SAMPLES = Path(__file__).resolve().parents[3] / "samples"
FILES = [
    ("arztbrief_muster-bauer.pdf", "application/pdf"),
    ("medikationsplan_muster-bauer.pdf", "application/pdf"),
    ("arztbrief_muster-bauer_foto.jpg", "image/jpeg"),
]


async def no_quota(principal) -> None:  # no database here; the retry is allowed
    return None


async def main(env_file: Path) -> int:
    env = read_env(env_file)
    key = env.get("MISTRAL_API_KEY", "")
    if not key:
        print("MISTRAL_API_KEY fehlt in", env_file)
        return 1
    ocr = MistralOcr(key, env.get("MISTRAL_OCR_MODEL") or "mistral-ocr-latest")
    llm = MistralLlm(key, env.get("MISTRAL_CHAT_MODEL") or "mistral-small-latest")
    extractor = Extractor(llm, no_quota)
    failures = 0
    for name, mime in FILES:
        print(f"\n=== {name}")
        try:
            result = await ocr.extract((SAMPLES / name).read_bytes(), mime)
        except OcrUnavailable as error:
            print("  OCR FEHLER:", error)
            failures += 1
            continue
        text = result.text
        print(f"  OCR ok: {len(result.pages)} Seite(n), {len(text)} Zeichen")
        print("  Anfang:", text[:160].replace("\n", " | "))
        try:
            suggestion = await extractor(None, name, text)
        except LlmUnavailable as error:
            print("  LLM FEHLER:", error)
            failures += 1
            continue
        data = suggestion.data
        if data is None:
            print("  LLM: kein Vorschlag (Schema zweimal verfehlt)")
            failures += 1
            continue
        print(f"  LLM ok: Modell {suggestion.model}")
        for key_name in ["doc_type", "document_date", "issuer", "resident_name"]:
            field = data[key_name]
            print(f"  {key_name:14} {field['proposed']!r:40} Fundstelle: {field['evidence_found']}")
        for med in data["medications"]:
            p = med["proposed"]
            found = med["evidence_found"]
            print(
                f"  Medikament     {p['name']} {p['strength']} {p['dosage']}  Fundstelle: {found}"
            )
        for diagnosis in data["diagnoses"]:
            found = diagnosis["evidence_found"]
            print(f"  Diagnose       {diagnosis['proposed']!r}  Fundstelle: {found}")
        for item in data["follow_ups"]:
            print(f"  Wiedervorlage  {item['proposed']}  Fundstelle: {item['evidence_found']}")
    print("\nErgebnis:", "alles ok" if failures == 0 else f"{failures} Fehler")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Aufruf: uv run python -m scripts.mistral_probe ../../.env")
    sys.exit(asyncio.run(main(Path(sys.argv[1]))))
