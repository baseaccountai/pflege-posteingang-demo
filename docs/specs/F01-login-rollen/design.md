# F01 – Login & Rollen: Design

## Überblick

```
Browser ──(Cookie __Host-pp_sid = zufällige ID)──▶ Next.js BFF ──(Bearer Access-Token + X-Bff-Assertion)──▶ FastAPI
                                                     │  │                                                     │ JWKS-Prüfung, Claims ableiten
                                                     │  └─ bff.sessions (Tokens AES-GCM-verschlüsselt)        ▼
                                                     ▼                                     Postgres: set local role authenticated
                                              Zitadel (OIDC)                               + set_config('request.jwt.claims', …) → RLS
```

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| OIDC-Client | `apps/web/src/lib/auth/oidc.ts` | `openid-client` v6: Discovery, Code + PKCE, Token-Einlösung, Refresh, `end_session`-URL |
| Login-Zwischenzustand | `apps/web/src/lib/auth/login-state.ts` | `state`, `nonce`, `code_verifier`, Rolle in einem kurzlebigen, verschlüsselten Cookie `__Host-pp_oidc` (10 min, `HttpOnly`); wird beim Callback sofort gelöscht → Einmalverwendung (AC5). Enthält **keine** Tokens. |
| Sitzungsspeicher | `apps/web/src/lib/auth/session-store.ts` | `postgres` (npm) als Rolle `bff_session` über den Pooler; Tokens AES-256-GCM mit `SESSION_ENC_KEY`; Tabelle speichert nur `sha256(sid)` |
| Sitzung | `apps/web/src/lib/auth/session.ts` | `getSession()`: Cookie → Hash → Zeile (nicht widerrufen, nicht abgelaufen) → bei Ablauf des Access-Tokens Refresh mit Zeilensperre (`select … for update`), damit parallele Anfragen nur einmal erneuern |
| Route-Handler | `apps/web/src/app/auth/{login,callback,logout}/route.ts` | Login (`?role=wb1|wb2|pdl`), Rücksprung, Logout (POST) |
| CSRF-Schutz | `apps/web/src/proxy.ts` | schreibende Methoden: `Origin` muss `APP_ORIGIN` sein, sonst 403 (AC15) |
| API-Client | `apps/web/src/lib/api.ts` | serverseitig: `Authorization: Bearer <access>`, `X-Bff-Assertion`: JWS (HS256, `BFF_API_SECRET`) mit `{sid_hash, aud: "pflege-api", iat, exp: +60 s}` |
| Rollenwechsel-UI | `apps/web/src/components/role-switcher.tsx` | drei Knöpfe + Zugangsdaten mit Kopieren; Wechsel = POST `/auth/logout?next=/auth/login?role=…` → **harter Seitenwechsel** (kein Client-Routing) |
| Token-Prüfung | `apps/api/app/auth/tokens.py` | PyJWT + `PyJWKClient` (Cache 10 min), erlaubte Algorithmen `RS256`, `ES256`; `iss`, `aud`, `exp`, `nbf`, Leeway 30 s |
| BFF-Nachweis | `apps/api/app/auth/bff.py` | prüft `X-Bff-Assertion` (Signatur, `aud`, `exp`), liefert `sid_hash` für Zähler (F02) |
| Claim-Mapping | `apps/api/app/auth/claims.py` | Rollen-Claim (konfigurierbar) → `Principal(sub, app_role, ward_ids, actor_type, display_name)` |
| DB-Zugriff | `apps/api/app/db.py` | `psycopg` (async) Pool als `api_gateway`, `prepare_threshold=None` (Transaktions-Pooler); `as_principal(principal)`: Transaktion, `set local role authenticated`, `set_config('request.jwt.claims', json, true)`; `set local` endet mit der Transaktion, auch bei Rollback |
| IdP-Setup | `infra/demo-users.json`, `infra/zitadel/setup.py` | Projekt, App, Rollen, Demo-Nutzer als Code; idempotent |
| Passwort-Wächter | `.github/workflows/demo-passwords.yml` | nur falls Spike S4 negativ: alle 15 min Demo-Passwörter per Management-API setzen |

## OIDC-Vertrag (Zitadel)

| Punkt | Festlegung |
|---|---|
| App-Typ | Web-Anwendung, Authorization Code, Client-Authentifizierung **Basic** (`OIDC_CLIENT_SECRET` nur in Vercel/`.env`), zusätzlich PKCE S256 – Rückfall laut Spike S2: PKCE-Client ohne Secret |
| Scopes | `openid profile offline_access urn:zitadel:iam:org:project:id:<PROJECT_ID>:aud urn:zitadel:iam:org:projects:roles` |
| Access-Token-Typ | **JWT** (Projekt-/App-Einstellung, nicht opak) |
| Rollen-Claim | `urn:zitadel:iam:org:project:roles` → Objekt `{ "nurse_wb1": { "<orgId>": "<domain>" } }`; ausgewertet werden nur die Schlüssel |
| `aud` | enthält die Projekt-ID (`OIDC_AUDIENCE`) |
| Redirect-URIs | `https://pflege-posteingang-demo.vercel.app/auth/callback`, `http://localhost:3000/auth/callback` |
| Post-Logout-URI | `https://pflege-posteingang-demo.vercel.app/`, `http://localhost:3000/` |
| Demo-Nutzer | `pflege-wb1`, `pflege-wb2`, `pdl` (Passwörter öffentlich auf der Startseite) |

Das Setup-Skript nutzt die Management-API mit dem Personal Access Token eines Service-Users (`ZITADEL_ADMIN_PAT`, nur in `.env` und GitHub-Secrets).

**Test-OIDC-Server (CI, lokal):** `ghcr.io/navikt/mock-oauth2-server` mit Konfiguration, die dieselben Rollen-Claims ausgibt. Er beweist zugleich die IdP-Austauschbarkeit (AC19).

## Datenmodell

Migration `<ts>_f01_auth.sql`: Schema `app` mit Hilfsfunktionen; `wards`, `residents` mit Policies; Rollen `api_gateway`, `bff_session`; Schema `bff` mit `sessions`; `revoke all from anon`. Details: [Datenmodell](../datenmodell.md).

## Schnittstellen (API)

| Methode | Pfad | Antwort | Rechte |
|---|---|---|---|
| GET | `/me` | `{sub, app_role, ward_ids, display_name}` | Token + BFF-Nachweis |
| GET | `/residents` | Liste eigener Bewohner (F04 erweitert) | `nurse`, `pdl` |
| GET | `/residents/{id}` | Bewohner oder **404** (fremd = nicht vorhanden) | `nurse`, `pdl` |

Fehler: 401 (Token/BFF-Nachweis ungültig oder fehlt), 403 (keine bekannte Rolle), 404 (nicht gefunden oder fremder WB – bewusst gleich). `/health`, `/health/ready` ohne Anmeldung.

## Sicherheitsaspekte

| Bedrohung | Gegenmaßnahme | AC |
|---|---|---|
| Token-Diebstahl per XSS | Tokens nur serverseitig; Cookie enthält nur zufällige ID | AC3, AC4 |
| Diebstahl der Sitzungstabelle | nur Hash der Sitzungs-ID, Tokens AES-GCM-verschlüsselt, Schlüssel nur in Vercel | AC3 |
| Login-CSRF, Replay des Rücksprungs | `state`, `nonce`, PKCE, Einmal-Cookie | AC1, AC5 |
| CSRF auf schreibende Aktionen | `Origin`-Prüfung + `SameSite=Lax`, keine GET-Mutationen | AC15 |
| Gefälschte/fremde Tokens | JWKS, `iss`/`aud`/`exp`, feste Algorithmen (kein `none`, kein HS*) | AC6 |
| Direktaufruf der API am BFF vorbei | BFF-Nachweis mit kurzer Gültigkeit | AC8 |
| Programmierfehler öffnet fremden WB | RLS erzwungen, zusammengesetzte Fremdschlüssel, `api_gateway` ohne `bypassrls` | AC9–AC11 |
| Claim-Reste auf gepoolter Verbindung | nur `set local` in Transaktion; Test Fehler→Rollback→andere Rolle | AC10 |
| Existenz-Leck fremder Bewohner | einheitlich 404 / Bildschirm 8 | AC12 |
| Daten der alten Rolle nach Wechsel | serverseitiger Widerruf, `no-store`, harter Seitenwechsel | AC13, AC14 |
| Demo-Konto wird durch Passwortänderung gesperrt | Spike S4, sonst Rücksetzen alle 15 min | AC18 |

Vertrauensgrenzen (Browser ↔ BFF, BFF ↔ API, API ↔ DB) werden im [Bedrohungsmodell](../../security/threat-model.md) ergänzt.

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest (Tokens mit Test-Schlüsselpaar, JWKS gemockt) | AC6, AC7, AC8, AC19 |
| RLS / DB | pytest gegen lokales Supabase | AC9, AC10 (inkl. Rollback- und Paralleltest), AC11 |
| Integration | pytest + TestClient + lokales Supabase | AC6–AC12 |
| Unit Web | Vitest | AC2, AC20, Sitzungsverschlüsselung, Login-State-Einmalverwendung |
| End-to-End | Playwright gegen Test-OIDC-Server + lokales Supabase | AC1, AC3, AC4 (Suche nach Token-Mustern in HTML, Cookies, Storage, Netzwerkantworten), AC5, AC12–AC15, AC21 |
| Manuell (Abnahme) | Zitadel öffentlich | AC1, AC16, AC17, AC18 |
