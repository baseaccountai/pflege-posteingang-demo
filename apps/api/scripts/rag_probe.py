"""Real test of questions with sources (F05 Task 8) against Mistral and the local Supabase.

Run by the applicant in their own terminal, never in CI. Reads only MISTRAL_API_KEY from the
given .env file and never prints it. Resets the LOCAL database to the seed first (including
supabase/seed/04_chunks.sql from `make seed-chunks`):

    make rag-probe

For each question it prints the similarity of the best chunks (to calibrate
RAG_MIN_SIMILARITY: real hits should lie clearly above, off-topic questions below) and the
answer with its cited sources, given with the configured threshold.
About 7 embedding and 6 LLM calls.
"""

import asyncio
import sys
from pathlib import Path

from app.auth.principal import Principal
from app.config import Settings
from app.db import Database
from app.providers.embeddings import create_embedding_provider
from app.providers.llm import create_llm_provider
from app.rag.answer import ANSWER_SCHEMA, MAX_OUTPUT_TOKENS, build_prompt, check_answer
from app.rag.retrieval import retrieve
from scripts.provision_db_roles import read_env
from scripts.reset_demo import LOCAL_ADMIN_DSN, SEED_DIR, reset

WB1 = Principal(sub="probe-wb1", app_role="nurse", ward_ids=("wb1",), display_name="Probe WB1")
WB2 = Principal(sub="probe-wb2", app_role="nurse", ward_ids=("wb2",), display_name="Probe WB2")

# (who asks, question, what a good answer contains - for the reader of the output)
QUESTIONS = [
    (WB1, "Wie ist Ramipril bei Hr. Muster-Bauer dosiert?", "5 mg morgens, Medikationsplan"),
    (WB1, "Warum wurde Ibuprofen bei Fr. Beispiel abgesetzt?", "Magenbeschwerden"),
    (WB1, "Welche Diagnosen hat Hr. Probe?", "Vorhofflimmern, COPD"),
    (WB2, "Welche Kontrolle ist bei Hr. Exempel geplant?", "neurologische Kontrolle"),
    (WB1, "Welche Medikamente bekommt Fr. Testfeld?", "keine Treffer (WB2-Bewohnerin)"),
    (WB1, "Wann ist das nächste Sommerfest im Heim?", "keine Treffer (nicht in den Dokumenten)"),
]


async def probe(env_file: Path) -> None:
    key = read_env(env_file).get("MISTRAL_API_KEY", "")
    if not key:
        raise SystemExit(f"MISTRAL_API_KEY fehlt in {env_file}.")
    settings = Settings(llm_provider="mistral", mistral_api_key=key)
    embeddings, llm = create_embedding_provider(settings), create_llm_provider(settings)

    reset(LOCAL_ADMIN_DSN, sorted(SEED_DIR.glob("*.sql")))
    db = Database(LOCAL_ADMIN_DSN, max_size=2)
    await db.open()
    try:
        for principal, question, expected in QUESTIONS:
            print(f"\n=== {principal.ward_ids[0].upper()}: {question}\n    erwartet: {expected}")
            ranked = await retrieve(db, principal, embeddings, question, None, 0.0)
            for hit in ranked.hits:
                print(f"    {hit.similarity:.3f}  {hit.resident_name}, {hit.heading}")
            found = await retrieve(
                db, principal, embeddings, question, None, settings.rag_min_similarity
            )
            if not found.hits:
                print(f"    -> Keine Treffer (Schwelle {settings.rag_min_similarity})")
                continue
            system, user = build_prompt(question, found.hits)
            raw = await llm.structured(system, user, ANSWER_SCHEMA, MAX_OUTPUT_TOKENS)
            checked = check_answer(str(raw.get("answer", "")), found.hits)
            print(f"    -> {checked.answer}")
            for source in checked.sources:
                print(f"       Quelle: {source.resident_name}, {source.doc_type}, S. {source.page}")
    finally:
        await db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python -m scripts.rag_probe <pfad/zur/.env>")
    asyncio.run(probe(Path(sys.argv[1])))
