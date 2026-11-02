"""Report on the check of questions and agent tasks (F13-AC9, F07-AC15) - like in the app.

Run by the applicant in their own terminal, never in CI. Reads only MISTRAL_API_KEY from the
given .env file and never prints it. Resets the LOCAL database to the seed first, like
`make security-report`: the checker gets pseudonymised text, as in production (F06).

    make request-report
    make request-report ANWEISUNG=dokument   # comparison: the old document instruction

Each entry of tests/security/requests is checked exactly as a request in the app
(app/security/request_check.py): layer 1 only with the rules of the request categories,
layer 2 with the request instruction, one call per entry. The report goes to
docs/security/reports/<date>-anfragen.md. An unusable answer blocks in the app (fail
closed) but counts apart here, like in the document report.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

from app.config import Settings
from app.db import Database
from app.privacy.gateway import ModelGateway, create_gateway
from app.providers.llm.base import LlmUnavailable
from app.security.classifier import (
    QUESTION_MAX_CHARS,
    QUESTION_MAX_TOKENS,
    REQUEST_PROMPT,
    SYSTEM_PROMPT,
    UNUSABLE,
    _classify,
)
from app.security.evaluation import REQUESTS_DIR, Entry, load_corpus
from app.security.patterns import matching_rules
from app.security.request_check import REQUEST_CATEGORIES
from scripts.provision_db_roles import read_env
from scripts.reset_demo import LOCAL_ADMIN_DSN, SEED_DIR, reset
from scripts.security_report import (
    BACKOFF_SECONDS,
    PAUSE_SECONDS,
    REPORT_DIR,
    RETRIES,
    CheckerRun,
    build_report,
)

LIMITS = """## Grenzen

- **Korpus:** {attacks} Angriffe und {harmless} harmlose Anfragen sind wenig; ein einzelner
  Fehlalarm verschiebt die Rate um rund 4 Prozentpunkte. Alle Einträge stammen vom Autor der
  Prüfanweisung – erst Korpus, dann Anweisung, aber kein unabhängiges Red Team.
- **Abgrenzung:** Wünsche außerhalb des Rahmens der App (Dosis ändern, löschen, anderer
  Wohnbereich) zählen als harmlos (F07-AC15): Sie steuern die KI nicht um, und der Agent
  lehnt sie über seine Rechte ab (Schicht 4).
- **Klassifikator:** ein Modell (`{model}`), ein Lauf, ein Aufruf je Eintrag wie in der App;
  ein zweiter Lauf kann leicht abweichen.
- **Nicht verwertbare Urteile** zählen hier als nicht erkannt; in der App sperren sie die
  Anfrage mit eigener Meldung (F07-AC16). Der Lauf umgeht das Tageskontingent des Backends.
- **Keine adaptiven Angreifer:** Wer die Anweisung kennt, formuliert um – deshalb begrenzen
  Rechte und menschliche Bestätigung die Wirkung, nicht die Erkennung allein.
"""


def request_rule_flags(entries: list[Entry]) -> set[str]:
    """Layer 1 as in the app: only rules that steer the AI itself (F07-AC9)."""
    return {
        e.id
        for e in entries
        if any(rule.category in REQUEST_CATEGORIES for rule in matching_rules(e.text))
    }


async def check_requests(
    gateway: ModelGateway,
    entries: list[Entry],
    pause: float = PAUSE_SECONDS,
    backoff: float = BACKOFF_SECONDS,
    instruction: str = REQUEST_PROMPT,
) -> CheckerRun:
    """Like classify_question in the app; `instruction` only to compare with the old one."""
    run = CheckerRun()
    for e in entries:
        verdict = None
        for attempt in range(RETRIES + 1):
            run.calls += 1
            try:
                (verdict,) = await _classify(
                    gateway, [e.text[:QUESTION_MAX_CHARS]], QUESTION_MAX_TOKENS, instruction
                )
                break
            except LlmUnavailable as error:
                print(f"  Aufruf {run.calls} fehlgeschlagen ({error}); Versuch {attempt + 1}")
                if attempt < RETRIES and backoff:
                    await asyncio.sleep(backoff * 2**attempt)
        if verdict is None:
            run.unchecked.add(e.id)
        elif verdict.category == UNUSABLE:
            run.unusable.add(e.id)
        elif verdict.injection:
            run.flagged.add(e.id)
        if pause:
            await asyncio.sleep(pause)
    return run


def build_request_report(
    entries: list[Entry],
    rule_flags: set[str],
    checker_flags: set[str],
    model: str,
    calls: int,
    day: date,
    unusable: set[str],
    unchecked: set[str],
) -> str:
    return build_report(
        entries, rule_flags, checker_flags, model, calls, day, unusable, unchecked,
        title="Prüfung von Fragen und Agent-Aufträgen",
        corpus="harmlose Anfragen (`apps/api/tests/security/requests/`)",
        limits=LIMITS,
    )  # fmt: skip


async def run(env_file: Path, old_instruction: bool = False) -> Path:
    key = read_env(env_file).get("MISTRAL_API_KEY", "")
    if not key:
        raise SystemExit(f"MISTRAL_API_KEY fehlt in {env_file}.")
    settings = Settings(llm_provider="mistral", mistral_api_key=key)
    entries = load_corpus(REQUESTS_DIR)

    reset(LOCAL_ADMIN_DSN, sorted(SEED_DIR.glob("*.sql")))
    db = Database(LOCAL_ADMIN_DSN, max_size=2)
    await db.open()
    try:
        gateway = create_gateway(settings, db)  # the checker sees placeholders only (F06)
        print(f"Prüfe {len(entries)} Anfragen mit {gateway.guard_model} …")
        instruction = SYSTEM_PROMPT if old_instruction else REQUEST_PROMPT
        checked = await check_requests(gateway, entries, instruction=instruction)
    finally:
        await db.close()

    day = date.today()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    suffix = "-dokumentanweisung" if old_instruction else ""
    path = REPORT_DIR / f"{day:%Y-%m-%d}-anfragen{suffix}.md"
    report = build_request_report(
        entries, request_rule_flags(entries), checked.flagged, gateway.guard_model,
        checked.calls, day, checked.unusable, checked.unchecked,
    )  # fmt: skip
    path.write_text(report + "\n", encoding="utf-8")
    print(f"Bericht: {path} ({checked.calls} Aufrufe)")
    return path


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or sys.argv[2:] not in ([], ["dokument"]):
        raise SystemExit("Aufruf: python -m scripts.request_report <pfad/zur/.env> [dokument]")
    asyncio.run(run(Path(sys.argv[1]), old_instruction=sys.argv[2:] == ["dokument"]))
