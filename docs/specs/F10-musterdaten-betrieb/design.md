# F10 – Musterdaten, Reset, Hinweise: Design

## Musterdaten

| Datei | Inhalt |
|---|---|
| `supabase/seed/01_wards_residents.sql` | WB1: Hr. Muster-Bauer, Fr. Beispiel, Hr. Probe · WB2: Fr. Testfeld, Hr. Exempel, Fr. Vorlage (alle erfunden) |
| `supabase/seed/02_documents.sql` | ältere Musterdokumente (Status `approved`) inkl. `document_files` (PDF mit Wasserzeichen) und `ocr_pages`; **erzeugt** von `samples/generate.py` (`make samples`), damit Datei und Text zusammenpassen; nicht die Upload-Muster aus `samples/`, denn die sind neuer als die Akte |
| `supabase/seed/03_record.sql` | Medikationen mit `medication_events`, Diagnosen, Wiedervorlagen mit Herkunft; ein Eintrag `actor_type='agent'` für F04-AC6 |
| `supabase/seed/chunks.jsonl` | vorberechnete Chunks + Embeddings (einmalig mit echtem Mistral, Skript `apps/api/scripts/build_seed_chunks.py`) |
| `apps/web/src/content/sample-record.json` | statische Musterakte (Fr. Beispiel) für `/muster`, erzeugt aus dem Seed (`make sample-record`: lokales Supabase zurücksetzen, Akte über die API-Funktion `get_record` als Pflegekraft WB1 unter RLS lesen); seed-relative Zeitpunkte als Kalendertage + `generated_on`, die Seite verschiebt sie auf heute; Originale als `apps/web/public/muster/<id>.pdf`; DB-Test prüft Übereinstimmung mit dem Seed |
| `samples/generate.py` | PDFs/Bilder (reportlab + Pillow) mit diagonalem Wasserzeichen „MUSTER“; `samples/bad/` per Bildfilter |

Ein Medikationsplan in `samples/` ist bewusst **neuer** als der Seed-Stand (ein Medikament neu, eins abgesetzt, eins geändert), damit der Abgleich (F03-AC7) sofort vorführbar ist.

## Reset

| Schritt | Umsetzung |
|---|---|
| Zeitplan | `.github/workflows/nightly-reset.yml` mit zwei Cron-Einträgen `0 1 * * *` und `0 2 * * *` (UTC); der Job läuft nur weiter, wenn es in `Europe/Berlin` 03 Uhr ist → ganzjährig 03:00 |
| Koordination | Der Reset ist **eine** Transaktion, die zuerst die Besuchertabellen per `TRUNCATE` leert. `TRUNCATE` nimmt exklusive Tabellensperren: er wartet auf laufende Transaktionen der API und blockiert neue bis zum Commit – niemand sieht einen halben Reset. Hintergrundverarbeitung, die vorher begann, findet ihr Dokument danach nicht mehr (die `update`s treffen 0 Zeilen) und schreibt nichts. *(Umsetzung 28.10.2026: ersetzt den ursprünglich geplanten Advisory-Lock mit `reset_generation`, der dasselbe nur mit mehr Code geleistet hätte; Tests in `apps/api/tests/rls/test_reset.py`.)* |
| 1. Wartung an | `system_state.maintenance = true` – nur für die Meldung an Besucher (AC7), nicht für die Korrektheit; die API prüft das Flag per `app.in_maintenance()` vor jeder schreibenden Anfrage (Middleware) und antwortet mit 503 `{error_code: "maintenance"}` |
| 2. Datenbank | **eine** Transaktion (`lock_timeout` 30 s): Besuchertabellen leeren (Dateien liegen in `document_files`, also mit drin), `bff.sessions` leeren, Seeds einspielen, `chunks.jsonl` laden (ab Aufgabe 3); `usage_counters` bleibt unberührt (AC6). Skript `apps/api/scripts/reset_demo.py` |
| 3. Wartung aus | auch im Fehlerfall (`finally`) |
| Wiederholbarkeit | jeder Lauf erzeugt denselben Endstand (AC8) |
| Rechte | **einziger** Ort mit DB-Admin-Zugang (`SUPABASE_DB_ADMIN_URL` nur als GitHub-Secret) |
| Lokal | `make reset` gegen lokales Supabase |

Da die Dateien in Postgres liegen (Entscheidung F02), ist der gesamte Reset eine Datenbank-Transaktion – kein Mischzustand zwischen Datenbank und Dateispeicher. Das Zurücksetzen der Demo-Passwörter regelt F01-AC18.

## Kosten- und Missbrauchsschutz

- `quota_limits(kind, scope, max_count)`: `upload/session/5` (gilt für die **ganze Sitzung**, Zeitraum `lifetime`), `ocr_page/global/50`, `llm_call/global/100`, `embed_chunk/global/500` (je Kalendertag in `Europe/Berlin`; *28.10.2026 von 100/300 gesenkt, damit die Kostenrechnung ≤ 0,50 € ergibt, Migration `20261028020000_f10_cost_limits.sql`*); per Migration, änderbar per SQL, nicht durch Aufrufer.
- `usage_counters(period, kind, subject, count)` mit `period` = Datum (`2026-10-25`) für globale Kontingente bzw. `lifetime` für Sitzungskontingente; Primärschlüssel `(period, kind, subject)`.
- `app.consume_quota(kind text, subject text, amount int) returns boolean`: `security definer`, Eigentümer `quota_owner`, `set search_path = app, pg_temp`; `amount` muss 1–20 sein; Limit und Zeitraum werden aus `quota_limits` gelesen; ist `amount` größer als das Limit, sofort `false`; sonst `insert … values (period, kind, subject, amount) on conflict (period, kind, subject) do update set count = usage_counters.count + excluded.count where usage_counters.count + excluded.count <= limit returning` – damit ist auch die Erstbuchung begrenzt; `revoke execute … from public, anon`, `grant execute … to authenticated`. `subject` ist `'global'` oder der Sitzungs-Hash aus dem BFF-Nachweis (F01-AC8).
- Buchung **vor** dem externen Aufruf; wird der Aufruf nicht ausgeführt, verfällt die Buchung (konservativ).
- Längenbegrenzung: Extraktion ≤ 20 000 Zeichen Eingabe / 1500 Tokens Ausgabe; Fragen ≤ 6 Chunks × 800 Tokens / 600 Tokens Ausgabe.
- Kostenrechnung in ADR 0003 und als Code in `apps/api/app/costs.py` (DB-Test `tests/rls/test_daily_cost.py` liest die Limits aus `quota_limits`): `Tagesmaximum = OCR-Seiten × Seitenpreis + LLM-Aufrufe × (max. Eingabe × Eingabepreis + max. Ausgabe × Ausgabepreis) + Embedding-Chunks × 800 × Embeddingpreis`; Limits so wählen, dass das Ergebnis ≤ 0,50 € ist (AC11). Zusätzlich Monatslimit im Mistral-Konto (10 €).

## Hinweise in der App

| Komponente | Ort | Verhalten |
|---|---|---|
| `ApiStatusBoundary` | `apps/web/src/components/api-status.tsx` | Lesen: Timeout (5 s)/Netzfehler/502/503/504 → `ApiUnavailable` → Seite zeigt Startet-Hinweis + Link `/muster`, fragt alle 5 s `/api/status`, lädt bei Bereitschaft neu, max. 6 Versuche, dann „Demo gerade nicht erreichbar“. Schreiben: 503 `api_starting` mit „Demo startet gerade … (bis zu 30 Sekunden) – bitte gleich erneut versuchen.“ |
| Kontingent- und Wartungsmeldung | dort, wo geklickt wurde (Upload, Neuversuch, Freigabe, Erledigt) | der BFF reicht 429 (`daily_quota`, `session_upload_limit`) und 503 `maintenance` mit der `message` der API durch; die Komponenten zeigen sie an. *(Umsetzung 28.10.2026: statt eigener Komponenten `QuotaNotice`/`MaintenanceNotice` – die Meldungstexte kommen ohnehin von der API.)* |
| Statusprüfung | `apps/web/src/app/api/status/route.ts` | öffentlich, ohne Nutzerdaten: fragt `GET /health/ready` der API (5 s Timeout) → `{ready}` |
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
| DB | pytest + lokales Supabase | AC10 (parallele Aufrufe überschreiten Limit nicht; `amount` 0/negativ/zu groß abgelehnt; Erstbuchung über dem Limit und Limit 0 abgelehnt; Sitzungszähler über Mitternacht nicht zurückgesetzt; `anon` darf nicht ausführen; Limit nicht vom Aufrufer änderbar), AC5–AC8 (Upload anlegen → Reset → weg; Fehler mitten im Seed → alles zurückgerollt, Wartung aus; Zähler bleiben; zweiter Lauf gleiches Ergebnis), AC7 (Schreiben während Wartung → 503; laufende Hintergrundaufgabe über den Reset hinweg schreibt nichts mehr) |
| Unit Web | Vitest | AC12, AC13 (Hinweistexte, Neuversuch, Link), AC14 (Musterakte aus JSON) |
| End-to-End | Playwright mit API-Attrappe (503, 429, Verzögerung) | AC4 (Banner + Footer auf allen Seitentypen), AC12, AC13, AC14 (`/muster` bei gestoppter API) |
| Betrieb | GitHub Actions | AC5 (Zeitlogik als Unit-Test des Prüfschritts), AC9 (manueller `workflow_dispatch` vor Abnahme) |
