# F01 – Login & Rollen: Design

## Überblick

```
Browser ──(Cookie __Host-pp_session, verschlüsselt)──▶ Next.js BFF ──(Bearer Access-Token)──▶ FastAPI
                                                          │ OIDC Code+PKCE                     │ JWKS-Prüfung, Claims ableiten
                                                          ▼                                    ▼
                                                  Zitadel / Keycloak            Postgres: set local role authenticated
                                                                                + set_config('request.jwt.claims', …) → RLS
```

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| OIDC-Client | `apps/web/src/lib/auth/oidc.ts` | `openid-client` (v6): Discovery, Code+PKCE, Token-Einlösung, Refresh, Logout-URL |
| Session | `apps/web/src/lib/auth/session.ts` | Session-Inhalt als **JWE** (A256GCM, Schlüssel `SESSION_SECRET`, `jose`) im Cookie `__Host-pp_session`; max. 8 h |
| Route-Handler | `apps/web/src/app/auth/{login,callback,logout}/route.ts` | Login starten (`?role=wb1|wb2|pdl` → `login_hint`, `prompt=login`), Rücksprung, Logout |
| API-Proxy | `apps/web/src/lib/api.ts` | serverseitige Aufrufe der API mit Access-Token; Refresh bei Ablauf |
| Rollenwechsel-UI | `apps/web/src/components/role-switcher.tsx` | drei Knöpfe + Zugangsdaten mit Kopieren |
| Token-Prüfung | `apps/api/app/auth/tokens.py` | PyJWT + `PyJWKClient`, erlaubte Algorithmen `RS256`, `ES256`; `iss`, `aud`, `exp`, `nbf`, Leeway 30 s |
| Claim-Mapping | `apps/api/app/auth/claims.py` | Rollen-Claim (konfigurierbar) → `Principal(sub, app_role, ward_ids, actor_type, display_name)` |
| DB-Zugriff | `apps/api/app/db.py` | `psycopg` (async) Pool als `api_gateway`; Kontextmanager `as_principal(principal)`: Transaktion, `set local role authenticated`, `set_config('request.jwt.claims', json, true)` |
| IdP-Setup | `infra/zitadel/setup.py`, `infra/keycloak/realm-pflege.json` | Projekt, App, Rollen, Demo-Nutzer als Code |

### Entscheidung zur Freigabe: Session im verschlüsselten Cookie

Die Tokens liegen **verschlüsselt** (JWE) im `HttpOnly`-Cookie. JavaScript im Browser kann das Cookie nicht lesen, und ohne `SESSION_SECRET` ist der Inhalt wertlos. Alternative wäre ein serverseitiger Session-Speicher (z. B. Redis); das kostet einen weiteren Dienst und widerspricht „Next.js bleibt dünn“. Um unter 4 KB zu bleiben, wird das ID-Token nicht gespeichert (Logout per `client_id` + `post_logout_redirect_uri`).

## Datenmodell

Migration `supabase/migrations/<ts>_f01_wards_residents.sql`:
- Schema `app` mit Hilfsfunktionen `app.ward_ids()`, `app.role()`, `app.uid()`, `app.actor_type()` (lesen `current_setting('request.jwt.claims', true)::jsonb`).
- Tabellen `wards`, `residents` (siehe [Datenmodell](../datenmodell.md)), RLS aktiviert und **erzwungen** (`force row level security`).
- Policy `residents_select`: `using (ward_id = any(app.ward_ids()))`.
- Rolle `api_gateway` (`login`, `noinherit`, kein `bypassrls`), `grant authenticated to api_gateway`.

## Schnittstellen (API)

| Methode | Pfad | Antwort | Rechte |
|---|---|---|---|
| GET | `/me` | `{sub, app_role, ward_ids, display_name}` | gültiges Token |
| GET | `/residents` | Liste eigener Bewohner (F04 erweitert) | `nurse`, `pdl` |
| GET | `/residents/{id}` | Bewohner oder **404** (fremd = nicht vorhanden) | `nurse`, `pdl` |

Fehler: 401 (Token ungültig/fehlt), 403 (keine bekannte Rolle), 404 (nicht gefunden oder fremder WB – bewusst gleich).

## Identity Provider

| Einstellung | Zitadel | Keycloak |
|---|---|---|
| App-Typ | Web, Code + PKCE, Auth-Methode „none“ oder Basic | Client `pflege-web`, public + PKCE S256 |
| Access-Token | **JWT** (nicht opak) | JWT (Standard) |
| Rollen-Claim | `urn:zitadel:iam:org:project:roles` (Projekt-Rollen `nurse_wb1`, `nurse_wb2`, `pdl`) | Mapper schreibt dieselben Rollen in denselben Claim-Namen |
| `aud` | Projekt-ID | Audience-Mapper `pflege-api` |
| Demo-Nutzer | `pflege-wb1`, `pflege-wb2`, `pdl` mit festen Demo-Passwörtern | gleich |
| Redirect-URIs | `https://pflege-posteingang-demo.vercel.app/auth/callback`, `http://localhost:3000/auth/callback` | `http://localhost:3000/auth/callback` |

Das Setup-Skript nutzt die Zitadel-Management-API mit einem **Personal Access Token eines Service-Users** (`ZITADEL_ADMIN_PAT`, nur in `.env`). Es ist idempotent (vorhandene Objekte werden aktualisiert). Passwortänderung durch Demo-Nutzer: Zitadel-Self-Service für das Projekt deaktivieren, soweit möglich; zusätzlich setzt der nächtliche Reset (F10) die Demo-Passwörter zurück.

## Sicherheitsaspekte

| Bedrohung | Gegenmaßnahme | AC |
|---|---|---|
| Token-Diebstahl per XSS | Tokens nur serverseitig, Cookie `HttpOnly` + verschlüsselt | AC3, AC4 |
| CSRF auf Login/Callback | `state` + PKCE, `SameSite=Lax` | AC1, AC5 |
| Gefälschte/fremde Tokens | JWKS, `iss`/`aud`/`exp`, feste Algorithmen (kein `none`, kein HS*) | AC6 |
| Programmierfehler im Backend öffnet fremde WB | RLS erzwungen in der DB, `api_gateway` ohne `bypassrls` | AC8, AC9 |
| Existenz-Leck fremder Bewohner | einheitlich 404 / Bildschirm 8 | AC10 |
| Daten der alten Rolle nach Wechsel | Cookie löschen, `no-store`, harter Seitenwechsel statt Client-Navigation | AC11, AC12 |

Vertrauensgrenze BFF ↔ API und Claim-Ableitung werden im [Bedrohungsmodell](../../security/threat-model.md) ergänzt.

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest (Tokens mit Test-Schlüsselpaar signiert, JWKS gemockt) | AC6, AC7, AC15 |
| RLS / Rechte | pytest gegen lokales Supabase (`supabase start`) | AC8, AC9 |
| Integration | pytest + TestClient + lokales Supabase | AC6–AC10 |
| Unit Web | Vitest | AC2, AC16, Session-Verschlüsselung (AC3) |
| End-to-End | Playwright gegen lokales Keycloak (CI) | AC1, AC3, AC4, AC5, AC10, AC11, AC12, AC17 |
| Manuell (Abnahme) | Login gegen Zitadel öffentlich | AC1, AC13, AC14 |

CI: Job `rls` mit `supabase/setup-cli` + `supabase start`; Job `e2e-auth` mit Keycloak-Container.
