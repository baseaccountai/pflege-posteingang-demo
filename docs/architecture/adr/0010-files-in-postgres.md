# ADR 0010: Originaldateien in Postgres statt Supabase Storage

Status: angenommen · Datum: 25.10.2026 (Entscheidung des Bewerbers nach Codex-Review der Specs) · weicht von Design 5.6 ab

## Kontext
Das Backend greift „im Namen des Nutzers“ über `set local role authenticated` + Claims auf Postgres zu (F01). Supabase Storage prüft Rechte dagegen nur mit von Supabase signierten JWTs; unsere Claims gelten dort nicht automatisch. Vercel begrenzt Anfragen auf 4,5 MB.

## Entscheidung
Originaldateien liegen als `bytea` in `document_files` mit derselben Wohnbereichs-RLS wie `documents`. Fotos werden im Browser auf ≤ 2000 px verkleinert, Dateien sind höchstens 4 MB.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Supabase Storage mit selbst signierten Supabase-JWTs | zusätzlicher Spike, eigener Signaturschlüssel, Risiko vor dem 02.11. |
| Storage mit Service-Key | verletzt „nie Service-Key im Anfragepfad“ |

## Konsequenzen
+ Ein Rechtemodell für Daten und Dateien; der nächtliche Reset ist eine einzige Transaktion.
− Nicht für große Datenmengen gedacht; für eine Demo mit Tagesreset und wenigen kleinen Dateien unproblematisch.
