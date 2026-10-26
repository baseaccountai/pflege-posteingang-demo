# ADR 0007: Datenbankzugriff im Namen des Nutzers

Status: angenommen (Spike S1) · Datum: 26.10.2026 · Ergebnis Spike F01, Aufgabe 1

## Kontext
Das Backend soll nie mit Admin- oder Service-Rechten auf Bewohnerdaten zugreifen. Jede Abfrage soll durch Row Level Security auf die Wohnbereiche des angemeldeten Nutzers begrenzt sein (Datenmodell, Grundsätze). Die Nutzer melden sich bei Zitadel an, nicht bei Supabase Auth. Deshalb passen die OIDC-Token nicht direkt zu den Supabase-Policies (Risiko in arc42 §11).

## Entscheidung
- Das Backend verbindet sich mit der eigenen Login-Rolle `api_gateway` (`login noinherit nobypassrls`, ohne eigene Tabellenrechte, Mitglied von `authenticated`). Die Verbindung läuft direkt über Postgres (psycopg-Pool) und den **Transaction-Pooler** von Supabase (Port 6543), nicht über die REST-API.
- Jede Anfrage läuft in **einer Transaktion** mit `set local role authenticated` und `set_config('request.jwt.claims', <Claims>, true)`. Die Claims leitet das Backend aus dem geprüften OIDC-Token ab (`app/db.py`, `Database.as_principal`).
- Policies lesen die Claims über `app.ward_ids()` usw. Fehlen die Claims, liefern die Funktionen leere Werte, also keine Zeilen.
- `prepare_threshold=None`, weil der Transaction-Pooler keine serverseitig vorbereiteten Anweisungen über Transaktionen hinweg kennt.
- Passwörter der Login-Rollen setzt `apps/api/scripts/provision_db_roles.py`. Es wird nur lokal ausgeführt und schreibt die Werte ausschließlich in `.env`.

## Ergebnis des Spikes
| Prüfung | Lokal (Supabase CLI) | Cloud (Irland, Transaction-Pooler) |
|---|---|---|
| `tests/rls/test_ward_isolation.py`, 9 Fälle: ohne Filter, Rollback auf derselben Verbindung, 20 parallele Anfragen, ohne Claims, kein Insert, Gateway-Rolle ohne Tabellenrechte, `anon` ohne Zugriff | 9 bestanden | 9 bestanden (26.10.2026) |
| Gegenprobe: RLS deaktiviert | 5 fehlgeschlagen (Tests greifen) | – |

`set local role` und transaktionslokale `set_config` funktionieren über Supavisor im Transaktionsmodus. Zwischen Anfragen gehen keine Claims verloren und keine werden vermischt.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Service-Key und Filter im Anwendungscode | Ein vergessener `where` gibt fremde Wohnbereiche preis; widerspricht „Zugriff im Namen des Nutzers“ |
| Backend signiert Supabase-JWT, Zugriff über PostgREST | Der Supabase-JWT-Schlüssel liegt dann im Backend; zusätzlicher HTTP-Umweg; Claims landen ohnehin in `request.jwt.claims` |
| Supabase Third-Party-Auth mit Zitadel-Token | Rollen- und Wohnbereich-Claims müssten im IdP Supabase-konform geformt werden; Agenten-Token (Stufe 2) schwerer abbildbar |

## Konsequenzen
+ RLS schützt auch bei Programmierfehlern in Abfragen; die Rechte sind in SQL sichtbar und getestet.
+ Dieselbe Technik funktioniert für Agenten (Stufe 2): andere Claims, gleiche Policies.
− Das Backend ist für die richtige Ableitung der Claims vertrauenswürdig (Vertrauensannahme im Datenmodell).
− Jede Anfrage braucht eine explizite Transaktion.

## Offen
- **S3:** Verbindung des Next.js-BFF mit der Rolle `bff_session` aus einer Vercel-Funktion. Wird mit F01-Aufgabe 8 (Sitzung) geprüft.
- **S2/S4:** Ergebnisse des Zitadel-Spikes (Claims, Widerruf, `end_session`) werden hier ergänzt.
