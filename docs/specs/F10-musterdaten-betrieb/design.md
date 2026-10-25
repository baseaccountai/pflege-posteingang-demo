# F10 – Musterdaten, Reset, Hinweise: Design

## Musterdaten

| Datei | Inhalt |
|---|---|
| `supabase/seed/01_wards_residents.sql` | WB1: Hr. Muster-Bauer, Fr. Beispiel, Hr. Probe · WB2: Fr. Testfeld, Hr. Exempel, Fr. Vorlage (alle erfunden) |
| `supabase/seed/02_record.sql` | freigegebene Medikationen, Diagnosen, Wiedervorlagen mit Herkunft (`actor_type='human'`, ein Eintrag `agent` für die Darstellung F04-AC6) |
| `supabase/seed/03_documents.sql` + Storage-Upload | Dokumente zu den Einträgen (Status `approved`) |
| `supabase/seed/chunks.jsonl` | vorberechnete Chunks + Embeddings (einmalig mit echtem Mistral erzeugt, Skript `apps/api/scripts/build_seed_chunks.py`) |
| `samples/generate.py` | erzeugt PDFs/Bilder (reportlab + Pillow) mit diagonalem Wasserzeichen „MUSTER“; `samples/bad/` per Bildfilter (Weichzeichner, Drehung) |

Ein Medikationsplan in `samples/` ist bewusst **neuer** als der Seed-Stand (ein Medikament neu, eins abgesetzt, eins geändert), damit der Abgleich (F03-AC7) sofort vorführbar ist.

## Reset

| Teil | Umsetzung |
|---|---|
| Workflow | `.github/workflows/nightly-reset.yml`, `cron: "0 2 * * *"` (03:00 MEZ; im Sommer 04:00 – akzeptiert) |
| Skript | `apps/api/scripts/reset_demo.py`: eine DB-Transaktion (Tabellen leeren in Abhängigkeitsreihenfolge, Seeds einspielen, `chunks.jsonl` laden); danach Storage-Bucket leeren und Seed-Dateien hochladen; danach Demo-Passwörter im IdP setzen |
| Rechte | **einziger** Ort mit `service_role`/DB-Passwort (Secrets `SUPABASE_DB_URL`, `SUPABASE_SECRET_KEY`, `ZITADEL_ADMIN_PAT` nur in GitHub Actions) |
| Lokal | `make reset` mit lokalem Supabase |

## Kosten- und Missbrauchsschutz

- Tabelle `usage_counters` + Funktion `app.consume_quota(kind text, subject text, amount int, limit int) returns boolean` (`security definer`, `search_path` fest, nur `authenticated` darf ausführen; `insert … on conflict do update … returning`, atomar).
- Aufrufer: F02 (Upload pro Sitzung, OCR-Seiten global), F03/F05 (LLM-Aufrufe global).
- Limits per Env (`DAILY_OCR_PAGE_LIMIT`, `DAILY_LLM_CALL_LIMIT`, `SESSION_UPLOAD_LIMIT`).
- Kostenschätzung bei vollen Limits (in ADR 0003 nachtragen, sobald Preise geprüft): 100 OCR-Seiten + 300 Small-Aufrufe pro Tag ≈ wenige Cent bis ca. 0,50 €/Tag.

## Hinweise in der App

| Komponente | Ort | Verhalten |
|---|---|---|
| `ApiStatusBoundary` | `apps/web/src/components/api-status.tsx` | fängt Timeout (5 s)/502/503 → Startet-Hinweis, Neuversuch alle 5 s, max. 6 Versuche, dann „Demo gerade nicht erreichbar“ |
| `QuotaNotice` | `components/quota-notice.tsx` | bei 429 mit `error_code=daily_quota` bzw. `session_upload_limit` |
| Keep-alive | `.github/workflows/keep-alive.yml` | `cron: "0 6 */2 * *"`, ruft `GET /health/ready` (API prüft DB mit `select 1`) |

## Schnittstellen (API)

| Methode | Pfad | Response |
|---|---|---|
| GET | `/health/ready` | 200 `{db: "ok"}` · 503 wenn DB nicht erreichbar |

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest | AC3 (Generator: Wasserzeichen-Text vorhanden, Namen nur aus erlaubter Liste), AC9 (Quoten-Logik) |
| DB | pytest + lokales Supabase | AC9 (parallele Aufrufe überschreiten Limit nicht), AC5–AC7 (Reset: Upload anlegen → Reset → weg; Fehler in der Mitte → Rollback) |
| Unit Web | Vitest | AC10, AC11 (Hinweistexte, Neuversuch) |
| End-to-End | Playwright mit API-Attrappe (503, 429, Verzögerung) | AC4 (Banner auf allen Hauptseiten), AC10, AC11 |
| Betrieb | GitHub Actions | AC5 und AC8 laufen grün (manueller `workflow_dispatch` vor Abnahme) |
