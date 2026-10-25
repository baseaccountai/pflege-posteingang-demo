# F04 – Bewohnerakte: Design

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Liste | `apps/web/src/app/bewohner/page.tsx` | Server Component, Daten über BFF → API |
| Akte | `apps/web/src/app/bewohner/[id]/page.tsx` | Abschnitte als Karten (shadcn `Card`, `Badge`, `Tabs` auf dem Handy) |
| Herkunft | `components/provenance.tsx` | eine Zeile „Arztbrief vom 12.10. · freigegeben von Pflegekraft WB1 am 24.10.“ bzw. Agenten-Variante |
| Endpunkte | `apps/api/app/residents/routes.py` | Liste mit Zählern, Akte (eine Abfrage pro Abschnitt unter `as_principal`) |

Die Herkunft wird per Join auf `documents` gebildet; Medikamente über ihr letztes `medication_events`-Ereignis. Anzeigenamen der Freigebenden stehen in `confirmed_by_name` (Claim zum Freigabezeitpunkt), damit die Akte keine IdP-Abfrage braucht.

## Datenmodell

Keine eigene Migration: Alle Spalten (`confirmed_by_name`, `medication_events`, `follow_ups.done_by/done_by_name/done_at`) legt F03 laut [Datenmodell](../datenmodell.md) an.

## Schnittstellen (API)

| Methode | Pfad | Response |
|---|---|---|
| GET | `/residents` | `[{id, display_name, room, ward_id, has_new, open_follow_ups, overdue_follow_ups}]` |
| GET | `/residents/{id}/record` | `{resident, medications{active[], discontinued[]} (je mit `events[]`), diagnoses[], follow_ups[], documents[]}` jeweils mit `provenance` · 404 fremd/unbekannt |
| POST | `/follow-ups/{id}/done` | 200 · 404 fremd · 409 bereits erledigt |

## Sicherheitsaspekte

- Alle Abfragen unter `as_principal` → RLS; keine Bewohner-ID wird ohne RLS-Prüfung aufgelöst.
- Fremd = unbekannt = 404 (keine Existenz-Information).
- Seiten mit `no-store` (F01-AC12).

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Integration | pytest + lokales Supabase + Seed | AC1, AC2 (Zeitgrenzen mit festem „heute“), AC4, AC5, AC6, AC8, AC9 |
| Unit Web | Vitest | AC5, AC6 (`provenance.tsx` beide Varianten), AC4 (Darstellung abgesetzt) |
| End-to-End | Playwright (desktop + mobile) | AC1, AC3, AC7, AC9, AC10; nach F03-Freigabe erscheint Eintrag mit Herkunft |
