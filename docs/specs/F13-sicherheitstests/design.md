# F13 – Automatische Sicherheitstests mit Bericht: Design

## Überblick

| Teil | Wann | Kosten | Ergebnis |
|---|---|---|---|
| Korpus gegen Regeln (Schicht 1) | jede CI | 0 | Raten, Schwellen-Prüfung (AC3) |
| Szenario-Tests (Fake-Modelle) | jede CI | 0 | Wirkung der Schichten 3–5 (AC4) |
| Korpus gegen Regeln + echten Klassifikator | `make security-report`, Bewerber | ca. 2 Aufrufe je 10 Einträge (gebündelt), Mistral freies Kontingent | Bericht in `docs/security/reports/` (AC5) |

**Korpus:** JSON Lines, eine Datei je Quelle (`deepset.jsonl`, `bipia_style.jsonl`, `pflege.jsonl`, `benign_pflege.jsonl`). Aus deepset/prompt-injections werden die deutschen und ein Teil der englischen Einträge übernommen (Lizenz im Kopf der Datei). Harmlose Texte: Formulierungen aus Arztbriefen, Medikationsplänen, Überleitungsbögen – auch solche, die Regeln reizen („Dosis erhöhen auf …“ im ärztlichen Kontext, „bitte ignorieren Sie den vorigen Plan“).

**Trennung (F07-AC13):** Muster werden nur aus `patterns/` geladen; der Trennungstest vergleicht 30-Zeichen-Fenster. Regeln dürfen nicht nach dem Korpus „nachgezogen“ werden: Neue Korpuseinträge werden erst eingetragen, dann wird gemessen; die Schwellen in `thresholds.json` werden nur mit Begründung im Commit angehoben oder gesenkt.

**Runner:** `apps/api/scripts/security_report.py` (wie `rag_probe.py`): liest `MISTRAL_API_KEY` via `read_env`, nie ausgegeben; bündelt je 10 Einträge in einen Klassifikator-Aufruf; schreibt Markdown mit Tabellen.

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Korpus | `apps/api/tests/security/corpus/*.jsonl` | AC1, AC2 |
| Schwellen | `apps/api/tests/security/thresholds.json` | AC3 |
| CI-Tests | `apps/api/tests/security/test_corpus.py`, `test_scenarios.py` | AC3, AC4 (Teil des API-Jobs) |
| Bericht | `apps/api/scripts/security_report.py`, `make security-report` | AC5, AC6 |
| Verweise | `content/requirements-map.ts`, `/projekt`, `threat-model.md` | AC7, AC8 |

## Datenmodell

Keine Änderungen.

## Sicherheitsaspekte

- Korpus enthält Angriffstexte, aber keine echten Personendaten; deepset-Einträge werden auf Personendaten durchgesehen.
- Schlüssel nur im Runner des Bewerbers, nie in der CI.

## Tests je Ebene

| Ebene | Werkzeug | Abgedeckte Kriterien |
|---|---|---|
| Unit Backend | pytest | AC1 (Schema/Anzahl/Lizenz je Eintrag), AC2a (Kennzahlen an kleinem Beispiel nachgerechnet), AC3 |
| Integration | pytest + respx | AC4 |
| Unit Web | Vitest | AC7 (Link zeigt auf vorhandene Datei, wie F09-AC5) |
| Manuell | `make security-report` | AC5, AC6 |
