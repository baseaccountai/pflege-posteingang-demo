# F03 – Felder vorschlagen & freigeben: Design

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| LLM-Schnittstelle | `apps/api/app/providers/llm/base.py` | `class LlmProvider(Protocol)`: `async def structured(system, user, schema) -> dict`, `async def chat(messages) -> str`, `model_name` |
| Mistral | `providers/llm/mistral.py` | Chat Completions mit `response_format` JSON-Schema; Modell aus Konfiguration (`MISTRAL_CHAT_MODEL`, z. B. Mistral Small) |
| Ollama | `providers/llm/ollama.py` | `/api/chat` mit `format` = JSON-Schema (Phase 8 voll, Stufe 1: Adapter + Test-Attrappe) |
| Schema | `apps/api/app/extraction/schema.py` | Pydantic-Modell `DocumentSuggestion` → JSON-Schema |
| Extraktion | `extraction/service.py` | Prompt (Dokument als **Daten** in Begrenzern, Anweisung „nur belegte Werte“), Validierung, 1 Wiederholung, Fundstellenprüfung (AC3) |
| Bewohner-Abgleich | `extraction/resident_match.py` | normalisierter Namensvergleich (Nachname + Vorname/Initial, Umlaute), nur über `residents` unter RLS; eindeutig → Vorschlag, sonst keiner |
| Medikationsabgleich | `extraction/medication_diff.py` | reine Funktion: `diff(current: list[Med], proposed: list[Med]) -> list[MedChange]`; Vergleich über normalisierten Wirkstoff-/Handelsnamen |
| Freigabe | `documents/approval.py` | Transaktion unter `as_principal`, Sperre `select … for update` auf das Dokument (AC9) |
| Prüfansicht | `apps/web/src/app/posteingang/[id]/page.tsx` | Original + Formular (react-hook-form + zod), Bewohner-Auswahl, Badges neu/geändert/unverändert/abgesetzt |

## Datenmodell

Migration `<ts>_f03_record.sql`: `medications`, `diagnoses`, `follow_ups` (siehe Datenmodell), RLS `select/insert/update` eigener WB, **kein** `delete`-Recht für `authenticated`. Spalte `documents.suggestion jsonb` (Vorschlag + Modellname + Zeitpunkt).

## Schnittstellen (API)

| Methode | Pfad | Request | Response |
|---|---|---|---|
| GET | `/documents/{id}/suggestion` | – | `{suggestion, model, resident_candidate, medication_changes}` |
| POST | `/documents/{id}/medication-diff` | `{resident_id, medications[]}` | `medication_changes[]` (für Neuberechnung nach Korrektur) |
| POST | `/documents/{id}/approve` | `{resident_id, resident_confirmed: true, doc_type, document_date, diagnoses[], medications[], follow_ups[]}` | 200 · 409 bereits freigegeben · 422 ohne Bestätigung |
| POST | `/documents/{id}/reject` | – | 200 |

## Sicherheitsaspekte

| Risiko | Maßnahme | AC |
|---|---|---|
| Halluzinierte Werte, Dosis-Manipulation im Dokument | Mensch prüft jedes Feld; Fundstellenprüfung; Abgleich deterministisch | AC3, AC7, AC8 |
| Falscher Bewohner | Pflichtbestätigung, keine Vorauswahl bei Unsicherheit, Auswahl nur aus eigenem WB | AC5, AC6 |
| Doppelte Freigabe | Zeilensperre + Statusprüfung | AC9 |
| LLM sieht Rohtext (Stufe 1) | nur Musterdaten; ab Stufe 2 Pseudonymisierung (F06) | – |

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest | AC2 (Attrappe liefert Unsinn), AC3, AC6, AC7 (Tabellentests für `diff`), AC13 |
| Integration | pytest + LLM-Attrappe + lokales Supabase | AC1, AC5, AC8, AC9 (zwei parallele Freigaben), AC10, AC11 |
| Unit Web | Vitest | AC4, AC5 (Knopf deaktiviert ohne Bestätigung), AC12 |
| End-to-End | Playwright | Medikationsplan hochladen → Abgleich sichtbar → Bewohner bestätigen → freigeben → Akte (F04) |
| Realtest (klein) | echtes Mistral, 3 Musterdokumente | Felder korrekt, kein erfundenes Medikament |
