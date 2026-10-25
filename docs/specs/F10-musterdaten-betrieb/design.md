# F10 – Musterdaten, Reset, Hinweise: Design

## Musterdaten

| Datei | Inhalt |
|---|---|
| `supabase/seed/01_wards_residents.sql` | WB1: Hr. Muster-Bauer, Fr. Beispiel, Hr. Probe · WB2: Fr. Testfeld, Hr. Exempel, Fr. Vorlage (alle erfunden) |
| `supabase/seed/02_documents.sql` | Musterdokumente (Status `approved`) inkl. `document_files` (Inhalt aus `samples/`) und `ocr_pages` |
| `supabase/seed/03_record.sql` | Medikationen mit `medication_events`, Diagnosen, Wiedervorlagen mit Herkunft; ein Eintrag `actor_type='agent'` für F04-AC6 |
| `supabase/seed/chunks.jsonl` | vorberechnete Chunks + Embeddings (einmalig mit echtem Mistral, Skript `apps/api/scripts/build_seed_chunks.py`) |
| `apps/web/src/content/sample-record.json` | statische Musterakte für `/muster`, erzeugt aus dem Seed (`make sample-record`); Test prüft Übereinstimmung |
| `samples/generate.py` | PDFs/Bilder (reportlab + Pillow) mit diagonalem Wasserzeichen „MUSTER“; `samples/bad/` per Bildfilter |

Ein Medikationsplan in `samples/` ist bewusst **neuer** als der Seed-Stand (ein Medikament neu, eins abgesetzt, eins geändert), damit der Abgleich (F03-AC7) sofort vorführbar ist.

## Reset

| Schritt | Umsetzung |
|---|---|
| Zeitplan | `.github/workflows/nightly-reset.yml` mit zwei Cron-Einträgen `0 1 * * *` und `0 2 * * *` (UTC); der Job läuft nur weiter, wenn es in `Europe/Berlin` 03 Uhr ist → ganzjährig 03:00 |
| 1. Wartung an | `system_state.maintenance = true`; API prüft das Flag vor jedem Schreibzugriff und jeder Pipeline-Stufe (AC7) |
| 2. Warten | 10 s, damit laufende Hintergrundschritte ihr Flag-Check erreichen |
| 3. Datenbank | **eine** Transaktion: Besuchertabellen leeren (Dateien liegen in `document_files`, also mit drin), `bff.sessions` leeren, Seeds einspielen, `chunks.jsonl` laden; `usage_counters` bleibt unberührt (AC6) |
| 4. Wartung aus | auch im Fehlerfall (`finally`) |
| Wiederholbarkeit | jeder Lauf erzeugt denselben Endstand (AC8) |
| Rechte | **einziger** Ort mit DB-Admin-Zugang (`SUPABASE_DB_ADMIN_URL` nur als GitHub-Secret) |
| Lokal | `make reset` gegen lokales Supabase |

Da die Dateien in Postgres liegen (Entscheidung F02), ist der gesamte Reset eine Datenbank-Transaktion – kein Mischzustand zwischen Datenbank und Dateispeicher. Das Zurücksetzen der Demo-Passwörter regelt F01-AC18.

## Kosten- und Missbrauchsschutz

- `quota_limits(kind, scope, daily_limit)`: `upload/session/5`, `ocr_page/global/100`, `llm_call/global/300`, `embed_chunk/global/500` (per Migration, änderbar per SQL, nicht durch Aufrufer).
- `app.consume_quota(kind text, subject text, amount int) returns boolean`: `security definer`, Eigentümer `quota_owner`, `set search_path = app, pg_temp`; `amount` muss 1–20 sein; Limit wird aus `quota_limits` gelesen; `insert … on conflict (day, kind, subject) do update set count = count + amount where count + amount <= limit returning`; `revoke execute … from public, anon`, `grant execute … to authenticated`. `subject` ist `'global'` oder der Sitzungs-Hash aus dem BFF-Nachweis (F01-AC8).
- Buchung **vor** dem externen Aufruf; wird der Aufruf nicht ausgeführt, verfällt die Buchung (konservativ).
- Längenbegrenzung: Extraktion ≤ 20 000 Zeichen Eingabe / 1500 Tokens Ausgabe; Fragen ≤ 6 Chunks × 800 Tokens / 600 Tokens Ausgabe.
- Kostenrechnung in ADR 0003 (vor Phase 3, mit den Preisen aus dem Mistral-Konto): `Tagesmaximum = OCR-Seiten × Seitenpreis + LLM-Aufrufe × (max. Eingabe × Eingabepreis + max. Ausgabe × Ausgabepreis) + Embedding-Chunks × 800 × Embeddingpreis`; Limits so wählen, dass das Ergebnis ≤ 0,50 € ist (AC11). Zusätzlich Monatslimit im Mistral-Konto (10 €).

## Hinweise in der App

| Komponente | Ort | Verhalten |
|---|---|---|
| `ApiStatusBoundary` | `apps/web/src/components/api-status.tsx` | Timeout (5 s)/502/503 → Startet-Hinweis + Link `/muster`, Neuversuch alle 5 s, max. 6 Versuche, dann „Demo gerade nicht erreichbar“ |
| `QuotaNotice` | `components/quota-notice.tsx` | bei 429 mit `error_code=daily_quota` bzw. `session_upload_limit` |
| `MaintenanceNotice` | `components/maintenance-notice.tsx` | bei 503 mit `error_code=maintenance` |
| Musterakte | `apps/web/src/app/muster/page.tsx` | statisch aus `sample-record.json` |
| Keep-alive | `.github/workflows/keep-alive.yml` | `cron: "0 6 */2 * *"`, ruft `GET /health/ready` (API prüft DB mit `select 1`) |

## Schnittstellen (API)

| Methode | Pfad | Response |
|---|---|---|
| GET | `/health/ready` | 200 `{db: "ok"}` · 503 wenn DB nicht erreichbar |
| (alle schreibenden) | – | 503 `{error_code: "maintenance"}` während des Resets |

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest | AC3 (Generator: Wasserzeichen, nur erlaubte Namen), AC11 (Längenbegrenzung in Prompt-Bauern) |
| DB | pytest + lokales Supabase | AC10 (parallele Aufrufe überschreiten Limit nicht; `amount` 0/negativ/zu groß abgelehnt; `anon` darf nicht ausführen; Limit nicht vom Aufrufer änderbar), AC5–AC8 (Upload anlegen → Reset → weg; Fehler mitten im Seed → alles zurückgerollt, Wartung aus; Zähler bleiben; zweiter Lauf gleiches Ergebnis), AC7 (Schreiben während Wartung → 503) |
| Unit Web | Vitest | AC12, AC13 (Hinweistexte, Neuversuch, Link), AC14 (Musterakte aus JSON) |
| End-to-End | Playwright mit API-Attrappe (503, 429, Verzögerung) | AC4 (Banner + Footer auf allen Seitentypen), AC12, AC13, AC14 (`/muster` bei gestoppter API) |
| Betrieb | GitHub Actions | AC5 (Zeitlogik als Unit-Test des Prüfschritts), AC9 (manueller `workflow_dispatch` vor Abnahme) |
