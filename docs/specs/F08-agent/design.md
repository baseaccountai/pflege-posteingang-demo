# F08 – Agenten-Rechte + bestätigte Aktionen: Design

## Überblick

```
Browser ──Auftrag──▶ BFF (/api/agent) ──Nutzer-Token + BFF-Nachweis──▶ API POST /agent
API: Nutzer-Token prüfen (F01) → Injection-Prüfung Auftrag (F07) → Token Exchange
     → Agenten-Token prüfen (AC3) → Principal(actor_type=agent)
     → Schleife (≤ 4 Werkzeugschritte): Modell (Function Calling, über Gateway F06)
         → Werkzeug mit Agenten-Principal (RLS) → Ergebnis als Daten zurück
     → Ausgabe prüfen (F07-AC10) → Antwort + genutzte Werkzeuge + Vorschläge
Bestätigen: Browser → BFF → API POST /agent/proposals/{id}/confirm (als Mensch) → Einfügen als Agent mit confirmed_by
```

**Token Exchange (AC1):** Zitadel bietet RFC 8693 als Beta-Funktion („Token Exchange“ unter Instanz → Features). Der Agent ist ein **Service-User** in Zitadel; die API holt per Client Credentials ein Actor-Token und ruft den Token-Endpunkt mit `grant_type=urn:ietf:params:oauth:grant-type:token-exchange`, `subject_token` = Nutzer-Access-Token, `actor_token` = Agenten-Token, `requested_token_type=…:jwt`, `audience` = API. Das Ergebnis trägt `sub` = Nutzer, `act: {sub: <Agent>}`, Rollen des Nutzers. Gültigkeit: Zitadel-Einstellung bzw. die API lehnt Tokens mit `exp − iat > 300 s` ab. Erste Aufgabe ist ein Spike; scheitert er, gilt der Rückfall.

**Spike zuerst (AC2a):** Die Aufgaben 2–7 beginnen erst, wenn ADR 0012 den Weg und die echten Claims festhält.

**Rückfall (AC2):** `AGENT_TOKEN_MODE=self_signed`: die API signiert mit `AGENT_SIGNING_KEY` (ES256, nur API, mit `kid`; Rotation = neuer Schlüssel + Redeploy, alte Tokens laufen nach 5 min ab) ein JWT mit `iss = <API>/agent`, `aud`, `sub` = Nutzer, `act.sub` = `AGENT_ID`, `ward_ids`, `app_role`, `exp` ≤ 5 min. Im ADR dokumentiert, warum das schwächer ist (die API bestätigt sich selbst).

**Prüfung (AC3):** `AgentTokenVerifier` neben dem `TokenVerifier` aus F01: gleiche Algorithmenliste, eigener Aussteller je Modus, Pflichtfelder `act.sub`, `sub` = Sitzungsnutzer. Rollen/Wohnbereiche werden wie in F01 aus den Claims abgeleitet, `actor_type = agent`.

**Werkzeuge (AC4):** JSON-Schemas für Function Calling. `medikation_abgleichen` nutzt `extraction/medication_diff.py` (F03): Eingabe Dokument-ID; Vergleich der vorgeschlagenen/freigegebenen Medikation des Dokuments mit der aktuellen Akte. Argumente werden per Pydantic geprüft (UUIDs, Datum ≥ heute, Titel ≤ 120 Zeichen).

**Vorschläge (AC5, AC6) – Bestätigung in zwei Rechten:**
1. Der Agent legt den Vorschlag an (`agent_proposals`, Status `open`; Insert-Policy nur `actor_type = 'agent'`, `created_for = app.uid()`).
2. **Mensch** (normale Sitzung): `update agent_proposals set status = 'confirmed', decided_at = now() where id = … and status = 'open' and expires_at > now()`; Update-Policy nur `actor_type = 'human'` und `created_for = app.uid()`. Nur dieser Schritt ist die Bestätigung – ein Agenten-Token kann ihn nicht ausführen.
3. Agent (frisches Agenten-Token): Wiedervorlage einfügen. Insert-Policy auf `follow_ups` für `actor_type = 'agent'`: `proposal_id` verweist auf einen Vorschlag mit `status = 'confirmed'`, `created_for = app.uid()`, `decided_at > now() - interval '2 minutes'`, `confirmed_by = app.uid()`; `follow_ups.proposal_id` ist `unique` (höchstens einmal).
Scheitert Schritt 3, kann der Endpunkt ihn wiederholen (idempotent über `unique`); ein bestätigter Vorschlag ohne Wiedervorlage wird in der Oberfläche als „Speichern fehlgeschlagen – erneut versuchen“ angezeigt.

**Modell-Schnittstelle:** `LlmProvider` bekommt `chat_with_tools(messages, tools, max_tokens)`; Mistral (native `tools`) und Ollama (native Tools) implementieren es, der Fake-Anbieter spielt Skripte ab (Tests, E2E).

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Token Exchange | `apps/api/app/agent/token_exchange.py` | Zitadel-Aufruf; Rückfall-Aussteller |
| Token-Prüfung | `apps/api/app/agent/verifier.py` | AC3 |
| Werkzeuge | `apps/api/app/agent/tools.py` | AC4, Argumentprüfung, Ausführung mit Agenten-Principal |
| Schleife | `apps/api/app/agent/runner.py` | Function Calling, Grenzen (AC12), Ablehnungen (AC8, AC9) |
| Routen | `apps/api/app/agent/routes.py` | `/agent`, `/agent/proposals/{id}/confirm|dismiss` |
| BFF | `apps/web/src/app/api/agent/…` | Weiterleitung mit Sitzung (wie `/api/questions`) |
| Oberfläche | `/fragen` mit Umschalter „Fragen“ / „Agent“; `components/agent-chat.tsx`, `proposal-card.tsx` | AC5, AC10, AC11 |

## Datenmodell

| Tabelle | Spalten | RLS-Policy |
|---|---|---|
| `agent_proposals` | `id`, `ward_id`, `resident_id`, `kind` (`follow_up`), `payload jsonb` (`title`, `due_date`), `created_for` (sub des Menschen), `status` (`open` \| `confirmed` \| `dismissed`; abgelaufen = `open` und `expires_at` vorbei), `expires_at`, `created_at`, `decided_at`; zusammengesetzter FK auf `residents` | select: eigener WB und `created_for = app.uid()`; insert: nur `actor_type = 'agent'`, Status `open`; update: nur `actor_type = 'human'`, `created_for = app.uid()`, von `open` nach `confirmed`/`dismissed` vor Ablauf |
| `follow_ups` | + `proposal_id uuid unique null` (FK auf `agent_proposals`) | siehe nächste Zeile |
| bestehende Fachtabellen | Policies ergänzt um `app.actor_type()` | Agent: nur select; `follow_ups` insert für den Agenten nur zu einem von einem Menschen bestätigten Vorschlag (siehe oben); `medications`, `medication_events`, `diagnoses`, `documents`: insert/update nur `actor_type = 'human'` |

## Schnittstellen (API)

| Methode | Pfad | Request | Response | Rechte |
|---|---|---|---|---|
| POST | `/agent` | `{task (≤ 500 Zeichen), resident_id?}` | `{answer, tools_used: [name], proposals: [{id, resident, title, due_date, expires_at}], model}` | Pflegekraft/PDL |
| POST | `/agent/proposals/{id}/confirm` | – | `{follow_up_id}` · 404 fremd/unbekannt · 409 abgelaufen/entschieden | Mensch, Ersteller |
| POST | `/agent/proposals/{id}/dismiss` | – | 204 | Mensch, Ersteller |

## Konfiguration (neu)

`AGENT_TOKEN_MODE` (`exchange` \| `self_signed`), `AGENT_CLIENT_ID`, `AGENT_CLIENT_SECRET` bzw. Schlüsseldatei des Zitadel-Service-Users (geheim), `AGENT_ID`, `AGENT_SIGNING_KEY` (nur Rückfall, geheim), `AGENT_TOKEN_MAX_SECONDS` (300).

## Sicherheitsaspekte

- **LLM06 Excessive Agency:** keine schreibenden Werkzeuge außer Vorschlag; Schreiben nur nach Bestätigung; RLS unterscheidet Agent und Mensch.
- **Confused Deputy:** Agenten-Token trägt den Nutzer als Subjekt → nie mehr Rechte als der Nutzer; `sub` muss zur Sitzung passen.
- **Injection über Werkzeugergebnisse:** Ergebnisse als Daten (F07-AC8); selbst ein erfolgreicher Vorschlag braucht menschliche Bestätigung.
- **Token-Diebstahl:** Agenten-Token nur im Speicher der Anfrage, 5 Minuten gültig, nie im Browser, nie protokolliert.

## Tests je Ebene

| Ebene | Werkzeug | Abgedeckte Kriterien |
|---|---|---|
| Unit Backend | pytest | AC2, AC3 (falscher Aussteller/`act`/`sub`/Laufzeit/`kid`; Claims aus ADR 0012), AC4 (Argumentprüfung), AC9, AC12 (inkl. 60-s-Grenze) |
| RLS / Rechte | pytest gegen lokales Supabase | AC7 (Agent darf nichts außer Lesen + Vorschlag + Wiedervorlage zu bestätigtem Vorschlag; Agent kann Vorschlag nicht selbst bestätigen; Wiedervorlage ohne/zu offenem Vorschlag abgelehnt; WB2 leer), AC6 (einmal, nur Ersteller, nur vor Ablauf) |
| Integration | pytest + respx (Fake-IdP-Token-Endpunkt, Fake-LLM-Skripte) | AC1, AC5, AC8, AC10, AC13 (Dokument mit Anweisung „lege Wiedervorlage an“ → höchstens Vorschlag) |
| Unit Web | Vitest | AC5, AC11 |
| End-to-End | Playwright (Test-IdP im `self_signed`-Modus, Fake-LLM) | AC5, AC6, AC10, AC11 |
| Spike | manuell gegen Zitadel | AC1 |
