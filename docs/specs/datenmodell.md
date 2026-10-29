# Gemeinsames Datenmodell (Stufe 1)

Stand: 25.10.2026 · Status: freigegeben 25.10.2026 · Gilt für alle Specs; jede Spec nennt, welche Tabellen sie anlegt (Migration in ihrer `tasks.md`).

## Grundsätze

- **Jede Tabelle mit Bewohnerbezug hat `ward_id`** und RLS-Policies darauf. RLS ist aktiviert **und erzwungen** (`force row level security`).
- **Verweise können den Wohnbereich nicht wechseln:** Bewohner- und Dokumentverweise sind **zusammengesetzte Fremdschlüssel** mit `ward_id` (z. B. `(resident_id, ward_id) references residents(id, ward_id)`). Eine WB2-Zeile kann so keinen WB1-Bewohner und kein WB1-Dokument referenzieren.
- **Policies je Operation:** `select … using (ward_id = any(app.ward_ids()))`, `insert … with check (ward_id = any(app.ward_ids()))`, `update … using (…) with check (…)`. Ein Trigger verhindert Änderungen an `ward_id` und `resident_id` nach dem Anlegen. **Ausnahme:** `documents.resident_id` darf genau einmal von `null` auf den bestätigten Bewohner gesetzt werden (Freigabe, F03).
- **Kein `delete`** für `authenticated` auf Akten- und Dokumenttabellen (Ausnahme: `chunks`, abgeleitete Daten, F05).
- **Keine Rechte für `anon`:** `revoke all … from anon` auf allen Tabellen und Funktionen (Supabase stellt `public` über die REST-API bereit).
- **Zugriff im Namen des Nutzers:** Das Backend setzt pro Transaktion `set local role authenticated` und `set_config('request.jwt.claims', …, true)` (siehe F01-Design). Fehlen die Claims, liefern die Hilfsfunktionen leere Werte → keine Zeilen.
- **Vertrauensannahme:** Das Backend ist für die korrekte Ableitung der Claims vertrauenswürdig. RLS schützt vor Programmierfehlern in Abfragen, nicht vor einem kompromittierten Backend.
- IDs `uuid` (`gen_random_uuid()`), Zeitstempel `timestamptz`.

## Claims (vom Backend aus dem geprüften OIDC-Token abgeleitet)

| Claim | Beispiel | Bedeutung |
|---|---|---|
| `sub` | `2894…` | Nutzer-ID im IdP |
| `app_role` | `nurse` \| `pdl` | fachliche Rolle |
| `ward_ids` | `["wb1"]`, PDL: `["wb1","wb2"]` | erlaubte Wohnbereiche |
| `actor_type` | `human` (Stufe 2: `agent`) | Mensch oder Agent |
| `display_name` | `Pflegekraft WB1` | für Herkunftsangaben |

Hilfsfunktionen (Schema `app`, `stable`, `security invoker`): `app.ward_ids() → text[]` (leer, wenn Claims fehlen), `app.role()`, `app.uid()`, `app.actor_type()`, `app.display_name()`.

## Tabellen

| Tabelle | Wichtige Spalten | Angelegt in |
|---|---|---|
| `wards` | `id text` (`wb1`, `wb2`), `name` | F01 |
| `residents` | `id`, `ward_id`, `display_name`, `birth_date`, `room`; `unique (id, ward_id)` | F01 |
| `documents` | `id`, `ward_id`, `resident_id` (null bis Freigabe), `doc_type`, `status`, `error_code`, `ocr_pages jsonb` (`[{page, markdown}]`), `suggestion jsonb`, `suggestion_model`, `document_date`, `uploaded_by`, `upload_session`, `attempts`, `status_changed_at`, `approved_by`, `approved_by_name`, `approved_at`, `indexing_status`; `unique (id, ward_id)` | F02 |
| `document_files` | `document_id` (PK), `ward_id`, `mime`, `size_bytes`, `content bytea` (≤ 4 MB) | F02 |
| `medications` | `id`, `ward_id`, `resident_id`, `name`, `strength`, `dosage jsonb` (morgens/mittags/abends/nachts), `hint` (z. B. „bei Bedarf“, ≤ 500 Zeichen, seit 28.10.2026), `status` (`active` \| `discontinued`) | F03 |
| `medication_events` | `id`, `ward_id`, `medication_id`, `kind` (`new` \| `changed` \| `discontinued`), `document_id`, `before jsonb`, `after jsonb`, `actor_type`, `created_by`, `confirmed_by`, `confirmed_by_name`, `created_at` | F03 |
| `diagnoses` | `id`, `ward_id`, `resident_id`, `text`, `source_document_id`, `actor_type`, `created_by`, `confirmed_by`, `confirmed_by_name`, `created_at` | F03 |
| `follow_ups` (Wiedervorlagen) | wie `diagnoses` + `title`, `due_date`, `status` (`open` \| `done`), `done_by`, `done_by_name`, `done_at` | F03 (Erledigt-Regel F04: nur offene, `done_by` aus Claims) |
| `chunks` | `id`, `document_id`, `ward_id`, `resident_id`, `doc_type`, `document_date`, `page`, `heading`, `content`, `embedding vector(1024)`, `embedding_model` | F05 |
| `usage_counters` | `period text` (Datum oder `lifetime`), `kind`, `subject`, `count`; `primary key (period, kind, subject)` | F10 |
| `quota_limits` | `kind`, `scope` (`global` je Tag \| `session` je Sitzung), `max_count` | F10 |
| `system_state` | genau eine Zeile: `maintenance bool`, `updated_at` – nur der Reset (Admin) schreibt; API liest über `app.in_maintenance()` (security definer); für `authenticated` keine Tabellenrechte | F10 |

Aufzählungen:
- `doc_type`: `arztbrief` · `medikationsplan` · `ueberleitungsbogen` · `sonstiges`
- `documents.status`: siehe Zustandsautomat in F02-Design
- `indexing_status`: `pending` · `done` · `failed`

Herkunft eines Medikaments = letztes `medication_events`-Ereignis; „neu/geändert/abgesetzt in den letzten n Tagen“ wird aus `kind` und `created_at` der Ereignisse berechnet.

## Sitzungen (nicht über die REST-API erreichbar)

| Tabelle | Spalten | Zugriff |
|---|---|---|
| `bff.sessions` | `id_hash` (SHA-256 der Sitzungs-ID), `sub`, `app_role`, `display_name`, `tokens_enc bytea` (AES-256-GCM mit `SESSION_ENC_KEY`: Access-, Refresh-, ID-Token), `access_expires_at`, `created_at`, `expires_at` (max. 8 h), `revoked_at` | nur Rolle `bff_session` |
| `bff.login_attempts` | `state_hash` (SHA-256 des OIDC-`state`), `expires_at` (10 min) – Einmal-Login-Vorgang: der Rücksprung löscht die Zeile, bevor er den Code einlöst (F01-AC5) | nur Rolle `bff_session` |

Schema `bff` ist nicht in den von Supabase veröffentlichten Schemata.

## Rollen in Postgres

| Rolle | Zweck | Rechte |
|---|---|---|
| `api_gateway` | Login-Rolle des Backends | nur `set role authenticated`; kein `bypassrls`, keine eigenen Tabellenrechte |
| `authenticated` | Nutzer/Agent „im Namen von“ | Tabellenrechte wie oben + RLS |
| `bff_session` | Login-Rolle des Next.js-BFF | nur `select/insert/update/delete` auf `bff.sessions` (Logout löscht die Zeile) und `select/insert/delete` auf `bff.login_attempts` |
| `quota_owner` | Eigentümer von `app.consume_quota` | nur `usage_counters`, `quota_limits` |
| `service_role` / DB-Admin | nur Reset und Migrationen (F10, F11) | umgeht RLS – nie im Anfragepfad |

## Ergänzungen Stufe 2 (Entwurf 28.10.2026)

| Tabelle / Funktion | Änderung | Spec |
|---|---|---|
| `residents` | + `pseudonym text unique` (zufälliger Code, z. B. `A17`) | F06 |
| `app.pseudonym_directory()` | `security definer`: Pseudonym, Namensteile, Geburtsdatum aller Bewohner – `execute` nur für `api_gateway`, nicht für `authenticated` | F06 |
| `chunks` | `content` pseudonymisiert (Neuindizierung) | F06 |
| `documents` | `status` + `screening`; + `screening_result` (`clean` \| `suspicious`), + `screened_pages jsonb` (bereinigte Seiten, einzige Quelle für Feldvorschlag und Indizierung) | F07 |
| `injection_findings` | Befunde je Dokument (Schicht, Seite, Regel, Auszug ≤ 500 Zeichen); eigener WB, nur einfügen | F07 |
| `quota_limits` | + `guard_document` (20/Tag), `guard_question` (100/Tag), in der Kostenschätzung F10 enthalten | F07 |
| `agent_proposals` | Vorschläge des Agenten (15 min gültig); Agent fügt ein, Mensch entscheidet | F08 |
| `follow_ups` | + `proposal_id unique` | F08 |
| Policies | `app.actor_type() = 'agent'`: nur Lesen + bestätigte Wiedervorlage + Vorschlag | F08 |
| `audit_events`, `app.log_event()` | Protokoll: Zustandsänderungen per Trigger, Modell-/Blockier-Ereignisse über Funktion mit Aktionsliste; lesen nur PDL | F12 |
| Claims | `actor_type = agent`; Agenten-Token mit `act.sub`, `sub` = Nutzer | F08 |
