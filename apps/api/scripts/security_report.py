"""Report on the prompt-injection detection (F13-AC5, AC6) - rules and the real checker model.

Run by the applicant in their own terminal, never in CI. Reads only MISTRAL_API_KEY from the
given .env file and never prints it. Resets the LOCAL database to the seed first, like
`make rag-probe`: the checker gets pseudonymised text, as in production (F06), and the
placeholders come from the seed's residents.

    make security-report

Every corpus entry (tests/security/corpus) is checked by layer 1 (rules, local) and layer 2
(the checker model, 10 entries per call - about 21 calls for 204 entries). The report goes to
docs/security/reports/<date>-injection.md: rates per layer and per category, examples of
errors, model, date, number of calls and the limits of the measurement.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

from app.config import Settings
from app.db import Database
from app.privacy.gateway import ModelGateway, create_gateway
from app.security.classifier import classify_document
from app.security.evaluation import Entry, Result, evaluate, load_corpus
from app.security.patterns import matching_rules
from scripts.provision_db_roles import read_env
from scripts.reset_demo import LOCAL_ADMIN_DSN, SEED_DIR, reset

BATCH = 10  # entries per checker call (F13 design)
PAUSE_SECONDS = 1.2  # Mistral's free tier allows about one request per second
REPORT_DIR = Path(__file__).parents[3] / "docs" / "security" / "reports"
EXAMPLES = 8  # missed attacks shown per report
LAYERS = ("Schicht 1 (Regeln)", "Schicht 2 (Prüfmodell)", "Schicht 1 + 2")

LIMITS = """## Grenzen

- **Korpus:** {attacks} Angriffe und {harmless} harmlose Texte sind wenig; eine Rate von
  90 % kann bei dieser Größe einige Prozentpunkte daneben liegen. Die eigenen Einträge
  (Pflege-Angriffe, indirekte Injection) hat derselbe Autor geschrieben, der die Regeln
  geschrieben hat – erst Korpus, dann Messung, aber kein unabhängiges Red Team.
- **Sprachmix:** überwiegend Deutsch, ein Teil Englisch; andere Sprachen sind nicht
  gemessen, obwohl Angreifer sie nutzen können.
- **Klassifikator:** ein Modell (`{model}`) mit einem Prompt, ein Lauf; Modelle antworten
  nicht immer gleich, ein zweiter Lauf kann leicht abweichen.
- **Keine adaptiven Angreifer:** Der Korpus ist fest. Wer die Regeln kennt und seine
  Angriffe nachschärft, kommt weiter – deshalb begrenzen die Schichten 3 bis 5 (Trennung
  von Daten und Anweisungen, Rechte, menschliche Bestätigung) die Wirkung, statt sich auf
  die Erkennung zu verlassen.
- **Versteckte Schrift** wird hier nicht gemessen (nur Text); dafür gibt es die
  Szenario-Tests mit den präparierten PDFs (`tests/security/test_scenarios.py`).
"""


async def check_with_classifier(
    gateway: ModelGateway, entries: list[Entry], pause: float = PAUSE_SECONDS
) -> tuple[set[str], int]:
    """Ids the checker flags, and the number of calls made."""
    flagged: set[str] = set()
    calls = 0
    for start in range(0, len(entries), BATCH):
        batch = entries[start : start + BATCH]
        verdicts = await classify_document(gateway, [e.text for e in batch])
        calls += 1
        flagged |= {e.id for e, verdict in zip(batch, verdicts, strict=True) if verdict.injection}
        if pause:
            await asyncio.sleep(pause)
    return flagged, calls


def _cell(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _rate(rate) -> str:
    return f"{rate.percent} ({rate.hits}/{rate.total})"


def build_report(
    entries: list[Entry],
    rule_flags: set[str],
    checker_flags: set[str],
    model: str,
    calls: int,
    day: date,
) -> str:
    results: list[Result] = [
        evaluate(entries, lambda e: e.id in rule_flags),
        evaluate(entries, lambda e: e.id in checker_flags),
        evaluate(entries, lambda e: e.id in rule_flags or e.id in checker_flags),
    ]
    by_id = {e.id: e for e in entries}
    attacks = sum(e.is_attack for e in entries)
    lines = [
        f"# Prompt-Injection-Erkennung – Bericht vom {day:%d.%m.%Y}",
        "",
        f"Prüfmodell: `{model}` · Aufrufe des Prüfmodells: {calls} · "
        f"Korpus: {attacks} Angriffe, {len(entries) - attacks} harmlose Pflegetexte "
        "(`apps/api/tests/security/corpus/`)",
        "",
        "Ein Eintrag gilt als **erkannt**, wenn mindestens eine geprüfte Schicht ihn markiert. "
        "Erkennungsrate = erkannte Angriffe ÷ alle Angriffe; Fehlalarmrate = markierte "
        "harmlose Texte ÷ alle harmlosen Texte (F13-AC2a).",
        "",
        "## Je Schicht",
        "",
        "| Schicht | Erkennungsrate | Fehlalarmrate |",
        "|---|---|---|",
    ]
    for name, result in zip(LAYERS, results, strict=True):
        lines.append(f"| {name} | {_rate(result.detection)} | {_rate(result.false_alarms)} |")
    lines += [
        "",
        "## Je Kategorie",
        "",
        "Anteil markierter Einträge; bei `benign` ist das die Fehlalarmrate.",
        "",
        "| Kategorie | Anzahl | Regeln | Prüfmodell | kombiniert |",
        "|---|---|---|---|---|",
    ]
    for category in sorted(results[0].by_category):
        rates = [r.by_category[category] for r in results]
        cells = " | ".join(rate.percent for rate in rates)
        lines.append(f"| {category} | {rates[0].total} | {cells} |")
    combined = results[2]
    lines += ["", f"## Verpasste Angriffe (kombiniert, {len(combined.missed)})", ""]
    lines += [
        f"- `{i}` ({by_id[i].category}): {_cell(by_id[i].text)}" for i in combined.missed[:EXAMPLES]
    ] or ["- keine"]
    if len(combined.missed) > EXAMPLES:
        lines.append(f"- … und {len(combined.missed) - EXAMPLES} weitere")
    lines += ["", "## Fehlalarme (je Schicht)", ""]
    alarms = [
        f"- `{i}` – {name}: {_cell(by_id[i].text)}"
        for name, result in zip(LAYERS[:2], results[:2], strict=True)
        for i in result.false_alarm_ids
    ]
    lines += alarms or ["- keine"]
    lines += ["", LIMITS.format(attacks=attacks, harmless=len(entries) - attacks, model=model)]
    return "\n".join(lines)


async def run(env_file: Path) -> Path:
    key = read_env(env_file).get("MISTRAL_API_KEY", "")
    if not key:
        raise SystemExit(f"MISTRAL_API_KEY fehlt in {env_file}.")
    settings = Settings(llm_provider="mistral", mistral_api_key=key)
    entries = load_corpus()
    rule_flags = {e.id for e in entries if matching_rules(e.text)}

    reset(LOCAL_ADMIN_DSN, sorted(SEED_DIR.glob("*.sql")))
    db = Database(LOCAL_ADMIN_DSN, max_size=2)
    await db.open()
    try:
        gateway = create_gateway(settings, db)  # the checker sees placeholders only (F06)
        print(f"Prüfe {len(entries)} Einträge mit {gateway.guard_model} …")
        checker_flags, calls = await check_with_classifier(gateway, entries)
    finally:
        await db.close()

    day = date.today()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{day:%Y-%m-%d}-injection.md"
    report = build_report(entries, rule_flags, checker_flags, gateway.guard_model, calls, day)
    path.write_text(report + "\n", encoding="utf-8")
    print(f"Bericht: {path} ({calls} Aufrufe)")
    return path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python -m scripts.security_report <pfad/zur/.env>")
    asyncio.run(run(Path(sys.argv[1])))
