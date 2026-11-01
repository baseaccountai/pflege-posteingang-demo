"""Probe of the fully local mode against the real services (F11-AC20, `make smoke-local`).

    cd apps/api && LLM_PROVIDER=ollama OCR_PROVIDER=docling uv run python -m scripts.local_probe

Four checks, each with its duration - the same code paths the API uses:
1. Docling reads samples/arztbrief_muster-bauer.pdf (the text contains "Ramipril").
2. The field suggestion (Extractor, through the privacy gateway) finds Ramipril.
3. The agent's model answers a task with a tool call (function calling).
4. The embedding model gives a 1024-dimensional vector (column chunks.embedding).

Only invented sample data; the models get placeholders, as always (F06). Exit code 1 if a
check fails.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from app.agent.runner import SYSTEM_PROMPT as AGENT_PROMPT
from app.agent.tools import tool_schemas
from app.config import Settings
from app.db import Database
from app.extraction.service import Extractor
from app.privacy.gateway import create_gateway
from app.providers.ocr import create_ocr_provider
from scripts.reindex import LOCAL_GATEWAY_DSN, REINDEXER

SAMPLE = Path(__file__).parents[3] / "samples" / "arztbrief_muster-bauer.pdf"
DIMENSION = 1024


async def timed(name: str, check) -> bool:
    start = time.monotonic()
    try:
        ok, detail = await check()
    except Exception as error:  # the probe reports, it does not crash
        ok, detail = False, f"{type(error).__name__}: {error}"
    seconds = time.monotonic() - start
    print(
        f"{'ok   ' if ok else 'FEHLER'} {name} ({seconds:.0f} s){' - ' + detail if detail else ''}"
    )
    return ok


async def main() -> None:
    settings = Settings()
    if settings.llm_provider != "ollama" or settings.ocr_provider != "docling":
        sys.exit("Die Probe gilt dem lokalen Modus: LLM_PROVIDER=ollama OCR_PROVIDER=docling")
    db = Database(LOCAL_GATEWAY_DSN)
    await db.open()
    try:
        gateway = create_gateway(settings, db)
        text = ""

        async def ocr():
            nonlocal text
            result = await create_ocr_provider(settings).extract(
                SAMPLE.read_bytes(), "application/pdf"
            )
            text = result.text
            return "Ramipril" in text, f"{len(text)} Zeichen"

        async def suggestion():
            async def no_quota(_principal):  # the probe books nothing
                return None

            found = await Extractor(gateway, no_quota)(REINDEXER, "probe", text)
            data = json.dumps(found.data, ensure_ascii=False) if found.data else ""
            return "Ramipril" in data, found.model

        async def tool_call():
            messages = [
                {"role": "system", "content": AGENT_PROMPT},
                {
                    "role": "user",
                    "content": "Bewohner in deinem Wohnbereich:\nBewohner_K42 (bewohner_id "
                    "11111111-1111-1111-1111-111111111111)\n\nAuftrag: Welche Wiedervorlagen "
                    "hat Bewohner_K42?",
                },
            ]
            turn = await gateway.chat_with_tools(messages, tool_schemas(), 500)
            names = [call.name for call in turn.tool_calls]
            return bool(names), ", ".join(names) or f"kein Werkzeug: {turn.content[:80]!r}"

        async def embedding():
            (vector,) = await gateway.embed(["Ramipril 5 mg morgens"])
            return len(vector) == DIMENSION, f"{len(vector)} Dimensionen, {gateway.embedding_model}"

        results = [
            await timed("Docling liest den Musterbrief", ocr),
            await timed("Feldvorschlag mit Ollama", suggestion),
            await timed("Agent ruft ein Werkzeug auf", tool_call),
            await timed("Embedding", embedding),
        ]
    finally:
        await db.close()
    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
