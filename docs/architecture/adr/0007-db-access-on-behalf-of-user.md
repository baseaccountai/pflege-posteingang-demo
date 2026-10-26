# ADR 0007: Datenbankzugriff im Namen des Nutzers

Status: angenommen (Spikes S1, S2, S4) · Datum: 26.10.2026 · Ergebnis Spike F01, Aufgaben 1 und 2

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

## Spike S2 + S4: Zitadel liefert die Claims (26.10.2026)
Die Claims, aus denen das Backend `request.jwt.claims` ableitet, kommen aus dem Zitadel-Access-Token. Geprüft mit dem Wegwerf-Skript `apps/api/scripts/zitadel_spike.py` (`setup`, `login`) gegen die Instanz `pflege-posteingang-demo-rbni7a.eu1.zitadel.cloud`, echter Browser-Login als Testnutzer `spike-wb1` (nur Projektrolle `nurse_wb1`).

| Prüfung | Ergebnis |
|---|---|
| Web-App, Authorization Code + PKCE S256, Client-Secret per **Basic** | Code-Einlösung HTTP 200 – kein Rückfall auf öffentlichen PKCE-Client nötig |
| Access-Token-Typ | **JWT**, `RS256`, Header mit `kid`; Signatur, `iss`, `aud`, `exp` per JWKS (PyJWT) gültig |
| `aud` | `[<client_id>, <project_id>]` → `OIDC_AUDIENCE` = Projekt-ID |
| Rollen-Claim | `urn:zitadel:iam:org:project:roles` = `{"nurse_wb1": {"<orgId>": "<domain>"}}`; zusätzlich gleicher Inhalt unter `urn:zitadel:iam:org:project:<project_id>:roles` |
| Weitere Claims (Access-Token) | `sub`, `client_id`, `jti`, `iat`, `nbf`, `exp` – kein Name, keine E-Mail |
| ID-Token | `nonce` stimmt; enthält `sid`, `amr`, `auth_time` |
| Refresh-Token (`offline_access`) | wird ausgegeben |
| Widerruf Refresh-Token → erneuter Refresh | Widerruf 200, Refresh danach **400** (`invalid_request`) |
| Widerruf Access-Token → Introspektion | Widerruf 200, Introspektion `active=false`. Lokal per JWKS bleibt das JWT bis `exp` gültig. |
| Access-Token-Laufzeit | Standard 12 h; Konsole erlaubt nur ganze Stunden → auf **1 h** gesetzt (Messung: 3600 s) |
| App-Token gegen Zitadel-Auth-API (`PUT /auth/v1/users/me/password`) | **401** – App-Tokens taugen nicht für Zitadel-Selbstverwaltung |
| `end_session` mit `client_id` + `post_logout_redirect_uri`, **ohne** `id_token_hint` | 302 auf Zitadels Logout-Seite (`/ui/v2/login/logout`); nach einem Klick auf die Sitzung Rücksprung zur Post-Logout-URI. Fremde Post-Logout-URI → 400. |
| **S4:** Demo-Nutzer ändert eigenes Passwort in der Konsole (`/ui/console/users/me`) | **möglich** – Anmeldung mit dem neuen Passwort klappte |

### Folgen
- **Token-Laufzeit 1 h statt 5 min:** Ein gestohlenes Access-Token allein reicht nicht, weil Fach-Routen zusätzlich den BFF-Nachweis verlangen (F01-AC8), den nur das BFF für eine lebende Sitzung ausstellt. 5 min wären nur per Admin-API mit Instanz-Rechten (`IAM_OWNER`) setzbar – bewusst nicht gemacht.
- **Rollenwechsel ohne IdP-Logout** (Entscheidung Bewerber, F01-AC13 angepasst): Zitadels Logout-Seite verlangt einen Klick. Rollenwechsel = Tokens widerrufen, Sitzung löschen, direkt neuer Login mit `prompt=login`; nur „Abmelden“ geht über `end_session`.
- **S4 negativ → Passwort-Wächter nötig** (F01-AC18): Workflow `demo-passwords.yml` setzt die Demo-Passwörter alle 15 min zurück (F01-Aufgabe 7).
- Die App läuft mit `devMode`, damit `http://localhost:3000/auth/callback` erlaubt ist. Die Redirect-URIs bleiben trotzdem eine feste Liste.
- Der Setup-Service-User `pp-setup` hat nur `ORG_OWNER` (nicht Instanz-Admin); sein PAT liegt nur in `.env` (später GitHub-Secret).
- Token Exchange bietet die Instanz weiterhin nicht an (Discovery) → F08.

## Offen
- **S3:** Verbindung des Next.js-BFF mit der Rolle `bff_session` aus einer Vercel-Funktion. Wird mit F01-Aufgabe 8 (Sitzung) geprüft.
- Testnutzer `spike-wb1` wird in F01-Aufgabe 7 durch die Demo-Nutzer ersetzt und gelöscht.
