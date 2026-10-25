# F03 – Felder vorschlagen & freigeben: Design

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| LLM-Schnittstelle | `apps/api/app/providers/llm/base.py` | `class LlmProvider(Protocol)`: `async def structured(system, user, schema) -> dict`, `async def chat(messages) -> str`, `model_name` |
| Mistral | `providers/llm/mistral.py` | Chat Completions mit `response_format` JSON-Schema; Modell aus Konfiguration (`MISTRAL_CHAT_MODEL`, z. B. Mistral Small) |
| Ollama | `providers/llm/ollama.py` | `/api/chat` mit `format` = JSON-Schema (Phase 8 voll, Stufe 1: Adapter + Test-Attrappe) |
| Schema | `apps/api/app/extraction/schema.py` | Pydantic-Modell `DocumentSuggestion` → JSON-Schema |
| Extraktion | `extraction/service.py` | Prompt (Dokument als **Daten** in Begrenzern, Anweisung „nur belegte Werte, jeweils mit wörtlicher Fundstelle“), Eingabe auf 20 000 Zeichen gekürzt, `max_tokens` 1500, Validierung, 1 Wiederholung (zählt gegen das Kontingent), Fundstellenprüfung für **jeden** Wert (AC3) |
| Bewohner-Abgleich | `extraction/resident_match.py` | normalisierter Namensvergleich (Nachname + Vorname/Initial, Umlaute), nur über `residents` unter RLS; eindeutig → Vorschlag, sonst keiner |
| Medikationsabgleich | `extraction/medication_diff.py` | reine Funktion: `diff(current: list[Med], proposed: list[Med]) -> list[MedChange]`; Vergleich über normalisierten Wirkstoff-/Handelsnamen |
| Freigabe | `documents/approval.py` | Transaktion unter `as_principal`: Dokument sperren und Status prüfen (AC9) → Bewohner sperren (`select … from residents … for update`) → Abgleich neu berechnen und mit dem vom Client gesendeten `diff_hash` vergleichen (AC8a) → schreiben inkl. `medication_events` |
| Prüfansicht | `apps/web/src/app/posteingang/[id]/page.tsx` | Original + Formular (react-hook-form + zod), Bewohner-Auswahl, Badges neu/geändert/unverändert/abgesetzt |

## Datenmodell

Migration `<ts>_f03_record.sql`: `medications`, `medication_events`, `diagnoses`, `follow_ups` (siehe Datenmodell) mit zusammengesetzten Fremdschlüsseln auf Bewohner und Dokument, RLS `select/insert/update` eigener WB, **kein** `delete`; Trigger: Bei Dokumenten in `approved`/`rejected` sind die fachlichen Spalten (`status`, `resident_id`, `doc_type`, `document_date`, `ocr_pages`, `suggestion`, `approved_*`) unveränderlich; `indexing_status` bleibt für F05 änderbar. Der Vorschlag steht in `documents.suggestion` (je Feld `value`, `evidence`, `evidence_found`).

## Schnittstellen (API)

| Methode | Pfad | Request | Response |
|---|---|---|---|
| GET | `/documents/{id}/suggestion` | – | `{suggestion, model, resident_candidate, medication_changes}` |
| POST | `/documents/{id}/medication-diff` | `{resident_id, medications[]}` | `{medication_changes[], diff_hash}` (Neuberechnung nach Korrektur oder Bewohnerwechsel) |
| POST | `/documents/{id}/approve` | `{resident_id, resident_confirmed: true, diff_hash, doc_type, document_date, diagnoses[], medications[], follow_ups[]}` | 200 · 409 falscher Status oder Akte geändert (mit neuem Abgleich) · 422 ohne Bestätigung |
| POST | `/documents/{id}/reject` | – | 200 · 409 falscher Status |

## Sicherheitsaspekte

| Risiko | Maßnahme | AC |
|---|---|---|
| Halluzinierte Werte, Dosis-Manipulation im Dokument | Mensch prüft jedes Feld; Fundstellenprüfung; Abgleich deterministisch | AC3, AC7, AC8 |
| Falscher Bewohner | Pflichtbestätigung, keine Vorauswahl bei Unsicherheit, Auswahl nur aus eigenem WB | AC5, AC6 |
| Doppelte Freigabe, Freigabe gegen Verwerfen | Zeilensperre + Statusprüfung, Endzustände unveränderlich | AC9 |
| Zwei Pläne desselben Bewohners gleichzeitig | Bewohner-Sperre + Abgleich-Hash | AC8, AC8a |
| LLM sieht Rohtext (Stufe 1) | nur Musterdaten; ab Stufe 2 Pseudonymisierung (F06) | – |

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest | AC2 (Attrappe liefert Unsinn), AC3 (Fundstelle vorhanden/fehlt für Diagnose, Datum, Medikament, Wiedervorlage), AC6, AC7 (Tabellentests für `diff`), AC13 |
| Integration | pytest + LLM-Attrappe + lokales Supabase | AC1, AC5, AC8 (Ereignisse geschrieben), AC8a (zweiter Plan desselben Bewohners zwischen Anzeige und Freigabe), AC9 (parallele Freigaben; Freigabe gegen Verwerfen; Freigabe bei `processing`), AC10, AC11 |
| Unit Web | Vitest | AC4, AC5 (Knopf deaktiviert ohne Bestätigung), AC6a (Bewohnerwechsel setzt Bestätigung zurück), AC12 |
| End-to-End | Playwright | Medikationsplan hochladen → Abgleich sichtbar → Bewohner bestätigen → freigeben → Akte (F04) |
| Realtest (klein) | echtes Mistral, 3 Musterdokumente | Felder korrekt, kein erfundenes Medikament |
