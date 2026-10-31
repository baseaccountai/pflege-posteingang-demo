# F07 – Prompt-Injection-Schutz + Testdokumente: Design

## Überblick

Die Prüfung ist ein **neuer, gespeicherter Status** im Zustandsautomaten von F02 zwischen OCR und Feldvorschlag:

```
processing ──OCR fertig──▶ screening ──▶ extracting (liest nur screened_pages) ──▶ ready_for_review
                              └─ Klassifikator nicht erreichbar / Kontingent ─▶ failed (screening_unavailable)
failed ──Neuversuch──▶ processing (keine OCR) | screening (OCR vorhanden)   ← nie direkt nach extracting
```

Änderungen am F02-Automaten: Übergang `processing → extracting` entfällt, neu `processing → screening → extracting`; Neuversuch mit vorhandener OCR geht nach `screening` (bisher `extracting`). Ein Check-Constraint erzwingt: `status in ('extracting','ready_for_review','approved','rejected')` ⇒ `screening_result is not null and screened_pages is not null`. Hängen-Erkennung (F02-AC9) behandelt `screening` wie `processing` (5 min).

**Abschnitte:** Die OCR-Seiten werden mit der Strukturtrennung des Chunkers (F05) in Abschnitte zerlegt (Überschrift/Absatz/Tabelle). Befunde verweisen auf `(page, start, end)` im Markdown der Seite. Das Ergebnis wird als `screened_pages` (gleiches Format wie `ocr_pages`, verdächtige Abschnitte durch `[Abschnitt entfernt: verdächtig]` ersetzt) gespeichert; Feldvorschlag und Indexer lesen nur diese Spalte (AC5). `ocr_pages` bleibt für die Prüfansicht und die Anzeige der Befunde.

**Schicht 1 – Dokument prüfen:**
- *Versteckter Text (AC2):* `pypdf` geht die Inhaltsströme jeder Seite durch und verfolgt Füllfarbe (`rg`, `g`, `k`) und Textgröße (Textmatrix × Schriftgröße). Text mit Füllfarbe ≥ 0,95 Helligkeit oder effektiver Größe < 3 pt wird gesammelt. Taucht dieser Text auch im OCR-Ergebnis auf, wird dort derselbe Abschnitt markiert; sonst steht er als eigener Befund (Seite, Wortlaut). Unsichtbarer Text mit Rendermodus 3 (OCR-Ebene gescannter PDFs) wird normal geprüft, nicht automatisch als verdächtig gewertet.
- *Muster (AC3):* Regeldateien in `apps/api/app/security/patterns/*.toml` (id, Kategorie, Sprache, regulärer Ausdruck, Erklärung). Kategorien: `role_override`, `ignore_instructions`, `addresses_ai`, `exfiltration`, `dose_manipulation`, `tool_abuse`, `outbound_link`.

**Schicht 2 – Klassifikator (AC4):** Ein Aufruf je Dokument (alle Abschnitte nummeriert in einem Prompt, Ausgabe JSON `[{section, injection, category, reason}]`) bzw. je Frage. Modell `GUARD_MODEL` (Standard `ministral-8b-latest`), Aufruf über das Gateway aus F06 (also pseudonymisiert). Zwei Kontingente (Umsetzung 29.10.2026, damit die Tagesobergrenze von F10 hält): `guard_document` (20/Tag; ein Aufruf prüft höchstens 20 000 Zeichen, längere Dokumente brauchen mehrere Aufrufe; Antwort ≤ 560 Tokens, Begründung höchstens 6 Wörter – zuerst 400 ohne Längenvorgabe; der F13-Bericht vom 31.10.2026 zeigte abgeschnittene Antworten, sobald 9 Abschnitte markiert waren; mehr als 583 Tokens sprengen die Tagesgrenze von F10) und `guard_question` (100/Tag; Frage oder Agent-Auftrag ≤ 500 Zeichen; Antwort ≤ 100 Tokens). Kosten in `costs.py` zu den Preisen von Mistral Small (sichere Obergrenze), ADR 0003. Antwortform kompakt: `checked` (Anzahl geprüfter Abschnitte) und `flagged` (nur verdächtige); stimmt `checked` nicht, gelten alle Abschnitte als verdächtig. Ungültiges JSON oder fehlende Abschnitte → alle betroffenen Abschnitte verdächtig.

**Schicht 3 – Prompt-Aufbau (AC8):** Die Begrenzer-Logik aus `rag/answer.py` (`_defuse`) wandert nach `app/security/delimiters.py` und wird von F03, F05, F07-Klassifikator und F08 genutzt.

**Schicht 4 – Minimale Rechte:** RLS (F01), Agenten-Token und Bestätigungspflicht (F08), menschliche Freigabe vor Indizierung (F03). Keine eigene Implementierung in F07; F13 testet die Wirkung („durchgerutschte“ Injection kann nichts schreiben).

**Schicht 5 – Ausgabe prüfen (AC10):** `app/security/output.py`: verwirft Antworten mit `http(s)://`, `www.`, Markdown-Links/-Bildern, HTML-Tags; Agent-Werkzeugaufrufe nur aus der erlaubten Liste (F08). Zitatprüfung (F05-AC8a) bleibt.

**Nach dem Codex-Review Phase 6 (29.10.2026):** Für die Anwendungsrolle `authenticated` erlaubt ein zweiter Trigger (`documents_allowed_transition`) nur die Übergänge des Zustandsautomaten, z. B. kein `screening → approved`. Ein Abschnitt über 20 000 Zeichen wird in Teilen geprüft; ein verdächtiger Teil schließt den ganzen Abschnitt aus. Nicht umgesetzt (Vertrauensannahme des Datenmodells: das Backend ist vertrauenswürdig, RLS schützt vor Programmierfehlern, nicht vor einem kompromittierten Backend): Herkunftsnachweis für `screening_result` und für Chunk-Inhalte.

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Prüfdienst | `apps/api/app/security/screening.py` | Abschnitte bilden, Schicht 1 + 2 ausführen, Befunde speichern |
| Versteckter Text | `apps/api/app/security/hidden_text.py` | PDF-Inhaltsströme auswerten (AC2) |
| Muster | `apps/api/app/security/patterns/` | TOML-Regeln (AC3), getrennt vom Korpus (AC13) |
| Klassifikator | `apps/api/app/security/classifier.py` | Prompt, JSON-Auswertung, Fehler = verdächtig |
| Begrenzer, Ausgabe | `app/security/delimiters.py`, `app/security/output.py` | Schicht 3 und 5 |
| Pipeline | `app/documents/pipeline.py` | neuer Schritt, Ausschluss verdächtiger Abschnitte |
| Anzeige | `components/inbox-list.tsx`, Prüfansicht `posteingang/[id]` | Abzeichen „verdächtig“, Bildschirm „Angriff erkannt“ (AC6) |
| Musterdokumente | `samples/generate.py`, Kopie nach `apps/web/public/samples/` (Make-Ziel, Test auf Gleichheit) | zwei präparierte PDFs (AC12), Download im Posteingang (AC14) |

## Datenmodell

| Tabelle | Spalten | RLS-Policy |
|---|---|---|
| `documents` | `status` + Wert `screening`; + `screening_result text` (`clean` \| `suspicious`, null bis geprüft), + `screened_pages jsonb`; Check-Constraint siehe oben | unverändert |
| `injection_findings` | `id`, `document_id`, `ward_id`, `page`, `start_offset`, `end_offset`, `layer` (`hidden_text` \| `pattern` \| `classifier`), `rule_id`, `category`, `excerpt` (≤ 500 Zeichen), `created_at`; zusammengesetzter FK `(document_id, ward_id)` | select/insert eigener WB; kein update/delete für `authenticated`; Reset löscht |
| `quota_limits` | + `guard_document` (`global`, 20), `guard_question` (`global`, 100) | – |

## Schnittstellen (API)

| Methode | Pfad | Änderung |
|---|---|---|
| GET | `/documents`, `/documents/{id}` | + `screening`, `findings: [{layer, page, rule_id, category, excerpt, explanation}]` |
| POST | `/questions` | 422 `{error_code: injection_detected, message}` (AC9) |
| POST | `/documents/{id}/retry` | gilt auch für `screening_unavailable` |

## Sicherheitsaspekte

- **Klassifikator ist selbst angreifbar:** Text als Daten zwischen Begrenzern, feste JSON-Ausgabe, Fehler = verdächtig; er entscheidet nie allein (Schicht 1, 4, 5 bleiben).
- **Fail closed:** ohne Klassifikator keine Weiterverarbeitung (AC7).
- **Kein Volltext im Protokoll:** im Protokoll (F12) nur Regel-ID. `injection_findings.excerpt` (≤ 500 Zeichen) ist Dokumentinhalt wie `ocr_pages`: gleiche Rechte (eigener WB), Anzeige nur in der Prüfansicht, Löschung im nächtlichen Reset.
- **Falsch-Positive:** führen nur zum Ausschluss eines Abschnitts, nicht zum Verwerfen des Dokuments; Rate wird in F13 gemessen.

## Tests je Ebene

| Ebene | Werkzeug | Abgedeckte Kriterien |
|---|---|---|
| Unit Backend | pytest | AC2 (PDF mit weißer/winziger/Tr3-Schrift in Gray/RGB/CMYK), AC3, AC4 (ungültiges JSON = Treffer), AC5, AC10, AC13, AC14 (statische Kopien gleich `samples/`) |
| RLS / Rechte | pytest gegen lokales Supabase | `injection_findings` nur eigener WB, kein update/delete; Check-Constraint (kein `extracting` ohne Prüfergebnis) |
| Integration | pytest + respx | AC1 (auch Neuversuch nach `screening_unavailable` prüft erneut), AC5 (Fake-LLM sieht keinen verdächtigen Abschnitt, Indexer liest `screened_pages`), AC7, AC9 (inkl. Klassifikator nicht erreichbar), AC11 |
| Unit Web | Vitest | AC6 |
| End-to-End | Playwright | AC6, AC14 (Download sichtbar), AC12 (präpariertes Musterdokument hochladen → „verdächtig“ → Angriff erkannt; Fake-Klassifikator im Test-Stack) |
