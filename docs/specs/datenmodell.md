# Gemeinsames Datenmodell (Stufe 1)

Stand: 25.10.2026 · Status: Entwurf · Gilt für alle Specs; jede Spec nennt, welche Tabellen sie anlegt (Migration in ihrer `tasks.md`).

## Grundsätze

- **Jede Tabelle mit Bewohnerbezug hat eine Spalte `ward_id`** und eine RLS-Policy darauf. Rechte hängen nie nur am Backend-Code.
- **Zugriff im Namen des Nutzers:** Das Backend setzt pro Transaktion `set local role authenticated` und `request.jwt.claims` mit den geprüften Claims (siehe F01-Design). Policies lesen die Claims über Hilfsfunktionen.
- **Herkunft:** Jeder Akteneintrag hat `source_document_id`, `created_by` (Nutzer-ID aus dem IdP), `actor_type` (`human` | `agent`) und `confirmed_by`.
- IDs sind `uuid` (`gen_random_uuid()`), Zeitstempel `timestamptz`.

## Claims (vom Backend aus dem OIDC-Token abgeleitet)

| Claim | Beispiel | Bedeutung |
|---|---|---|
| `sub` | `2894…` | Nutzer-ID im IdP |
| `app_role` | `nurse` \| `pdl` | fachliche Rolle |
| `ward_ids` | `["wb1"]`, PDL: `["wb1","wb2"]` | erlaubte Wohnbereiche |
| `actor_type` | `human` (Stufe 2: `agent`) | Mensch oder Agent |
| `display_name` | `Pflegekraft WB1` | für Herkunftsangaben |

Hilfsfunktionen (Schema `app`, `stable`, `security invoker`): `app.ward_ids() → text[]`, `app.role() → text`, `app.uid() → text`, `app.actor_type() → text`.

## Tabellen

| Tabelle | Wichtige Spalten | Angelegt in | RLS |
|---|---|---|---|
| `wards` | `id text` (`wb1`, `wb2`), `name` | F01 | lesen: `id = any(app.ward_ids())` |
| `residents` | `id`, `ward_id`, `display_name`, `birth_date`, `room` | F01 | lesen: eigener WB |
| `documents` | `id`, `ward_id`, `resident_id` (null bis Freigabe), `doc_type`, `status`, `storage_path`, `ocr_markdown`, `suggestion jsonb`, `document_date`, `uploaded_by`, `approved_by`, `approved_at`, `error_code` | F02 | lesen/einfügen/ändern: eigener WB |
| `medications` | `id`, `ward_id`, `resident_id`, `name`, `strength`, `dosage`, `status` (`active` \| `discontinued`), `source_document_id`, `created_by`, `actor_type`, `confirmed_by`, `created_at`, `discontinued_at` | F03 | eigener WB; kein `delete` |
| `diagnoses` | `id`, `ward_id`, `resident_id`, `text`, `source_document_id`, Herkunftsspalten | F03 | eigener WB; kein `delete` |
| `follow_ups` (Wiedervorlagen) | `id`, `ward_id`, `resident_id`, `title`, `due_date`, `status` (`open` \| `done`), `source_document_id`, Herkunftsspalten | F03 | eigener WB; kein `delete` |
| `chunks` | `id`, `document_id`, `ward_id`, `resident_id`, `doc_type`, `document_date`, `page`, `heading`, `content`, `embedding vector(1024)` | F05 | lesen: eigener WB |
| `usage_counters` | `day date`, `kind` (`ocr_page` \| `llm_call` \| `upload`), `subject` (global oder Nutzer), `count` | F10 | kein direkter Zugriff; nur über `app.consume_quota()` (`security definer`) |

`doc_type`: `arztbrief` · `medikationsplan` · `ueberleitungsbogen` · `sonstiges`
`documents.status`: `uploaded` → `processing` → `ready_for_review` → `approved` · Fehlerpfade: `unreadable`, `failed`, `rejected` · (Stufe 2: `suspicious`)

## Speicher

Supabase Storage, Bucket `documents` (privat), Pfad `<ward_id>/<document_id>/<dateiname>`. Policies wie `documents`: nur eigener Wohnbereich.

## Rollen in Postgres

| Rolle | Zweck | Rechte |
|---|---|---|
| `api_gateway` | Login-Rolle des Backends | darf nur `set role authenticated`; **kein** `bypassrls`, keine Tabellenrechte |
| `authenticated` | Nutzer/Agent im Namen von | Tabellenrechte + RLS |
| `service_role` | nur Seed/Reset (F10) | umgeht RLS – nie im Anfragepfad |
