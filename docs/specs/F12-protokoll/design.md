# F12 – Protokoll für die Pflegedienstleitung: Design

## Überblick

Zwei Schreibwege, beide mit Eigentümer `audit_owner` (`security definer`):

1. **Trigger** auf `documents` (Insert, Statuswechsel), `agent_proposals` (Insert, Statuswechsel), `follow_ups`/`diagnoses`/`medication_events` (Insert) schreiben die Zustandsänderungen – atomar mit der Änderung (AC4, AC8).
2. **`app.log_event(action, outcome, model, document_id, resident_id, details)`** für Modell-, Frage-, Werkzeug- und Blockier-Ereignisse, mit fester Aktionsliste (AC9). Ein Principal kann so nur Ereignisse über sich selbst und nur dieser Arten erzeugen; das Restrisiko (falsche, aber eigene Modell-Ereignisse) ist im Bedrohungsmodell benannt.

Beide Sie liest Akteur, Akteur-Art, Anzeigename, „im Auftrag von“ und Wohnbereich aus `request.jwt.claims` (AC4) und prüft, dass `document_id`/`resident_id` zum Wohnbereich gehören. `authenticated` hat auf die Tabelle **keine** Schreibrechte, nur `execute` auf die Funktion; lesen darf per RLS nur `app.role() = 'pdl'`.

Im Backend ruft der Helfer `audit.log(principal, …)` `app.log_event` in einer eigenen kurzen Transaktion nach dem Modellaufruf auf (OCR und LLM laufen bewusst außerhalb von DB-Transaktionen, F02). Schlägt das fehl, wird die Antwort nicht ausgeliefert; eine Blockierung bleibt in jedem Fall bestehen (AC8).

Bei Agenten-Ereignissen ist der Akteur „KI-Agent“ und `on_behalf_of_name` der Anzeigename aus den Claims des Agenten-Tokens (= Nutzer). Ereignisse ohne Wohnbereich (z. B. Frage der PDL über alle Bereiche) haben `ward_id = null`.

`details` ist ein `jsonb` mit fester Erlaubnisliste von Schlüsseln (`rule_id`, `layer`, `tool`, `error_code`, `proposal_id`, `pages`); andere Schlüssel lehnt die Funktion ab (AC3).

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Migration | `supabase/migrations/…_f12_audit.sql` | Tabelle, Trigger, Funktion, Rolle `audit_owner`, RLS |
| Helfer | `apps/api/app/audit.py` | Aufruf aus Pipeline, Fragen, Agent, F06/F07-Blockierungen |
| Route | `GET /audit?before=&agent_only=&blocked_only=` | Seitenweise lesen als PDL |
| Seite | `apps/web/src/app/protokoll/page.tsx`, `components/audit-list.tsx` | AC6, AC7 |
| Navigation | `components/app-nav.tsx` | Eintrag nur für PDL |

## Datenmodell

| Tabelle | Spalten | RLS-Policy |
|---|---|---|
| `audit_events` | `id bigint identity`, `at timestamptz default now()`, `ward_id`, `action text`, `outcome text`, `actor_type`, `actor_sub`, `actor_name`, `on_behalf_of_name`, `model`, `document_id`, `resident_id`, `details jsonb` | select nur `app.role() = 'pdl'` und (`ward_id is null` oder `ward_id = any(app.ward_ids())`); kein insert/update/delete für `authenticated` (nur über `app.log_event`); Reset (Admin) leert |

## Schnittstellen (API)

| Methode | Pfad | Request | Response | Rechte |
|---|---|---|---|---|
| GET | `/audit` | `before` (id), `agent_only`, `blocked_only` | `{events: [...], next_before}` (50, sortiert `id desc`) | PDL; sonst 403 |

## Sicherheitsaspekte

- **Fälschung:** Akteur aus Claims, nicht aus Parametern (AC4); keine Tabellenrechte.
- **Datensparsamkeit:** keine Inhalte, keine Namen (AC3); Anzeige der Bewohner im Protokoll über ID → Name per RLS beim Lesen (PDL sieht alle WB).
- **Manipulation:** kein update/delete (AC5); nur der Reset mit Admin-Rechten leert die Tabelle nachts.

## Tests je Ebene

| Ebene | Werkzeug | Abgedeckte Kriterien |
|---|---|---|
| RLS / Rechte | pytest gegen lokales Supabase | AC4, AC5, AC6, AC8, AC9 (Pflegekraft liest nichts, kein direktes insert, kein update/delete, fremde Dokument-ID abgelehnt, unbekannter `details`-Schlüssel und Zustands-Aktion über `log_event` abgelehnt, Trigger-Ereignis entsteht mit der Änderung und fehlt bei Rollback) |
| Integration | pytest + TestClient | AC1, AC2, AC3 (kein Fragetext/Name im Ereignis), AC8 |
| Unit Web | Vitest | AC7 |
| End-to-End | Playwright | AC6, AC7 (PDL sieht Agent- und Blockiert-Ereignisse; WB1 sieht „Kein Zugriff“) |
