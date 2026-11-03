# F01 – Login & Rollen: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [x] **1. Spike S1 + S3: Datenbank im Namen des Nutzers** — `F01-AC9`, `F01-AC10`, `F01-AC11`
  - [x] Migration `f01_auth` (Schema `app`, `wards`, `residents`, Rollen, `bff.sessions`, `revoke … from anon`)
  - [x] `tests/rls/test_ward_isolation.py`: ohne Filter; WB1-Fehler→Rollback→WB2 auf derselben Verbindung; 20 parallele Anfragen gemischt; ohne Claims → 0 Zeilen und Schreibfehler → rot → `db.as_principal()` → grün
  - [x] Dieselben Tests gegen Cloud-Supabase über den Pooler (26.10.2026: 9 bestanden)
  - [x] BFF-Rolle von einer Vercel-Funktion (S3; 27.10.2026 bestanden: Login pflege-wb1 auf Vercel → Zeile in `bff.sessions` (wb1, 8 h), `login_attempts` verbraucht, Abmelden → Zeile gelöscht)
  - [x] ADR 0007 „Datenbankzugriff im Namen des Nutzers“; **Halt, falls S1 scheitert** (Bewerber informieren)
  - [x] Commit: `feat(db): add ward isolation with RLS (spike F01)`
- [x] **2. Spike S2 + S4: Zitadel** — Setup-Skript-Entwurf, Token holen, Claims/`aud`/Typ prüfen, Token-Widerruf und `end_session` mit `client_id` ohne `id_token_hint` prüfen, Passwortänderung als Demo-Nutzer versuchen; Ergebnis in ADR 0007 · Commit (26.10.2026: S2 bestanden, S4 negativ → Passwort-Wächter in Aufgabe 7)
- [x] **3. Token-Prüfung** — `F01-AC6`, `F01-AC19`
  - [x] `tests/auth/test_tokens.py`: gültig, abgelaufen, `nbf` in Zukunft, falscher `iss`, falscher `aud`, `alg=none`, `HS256` mit Public Key, unbekannter `kid` → rot → `tokens.py` → grün · Commit `feat(api): verify OIDC access tokens via JWKS`
- [x] **4. BFF-Nachweis** — `F01-AC8`
  - [x] Tests: fehlt, abgelaufen, falsche Signatur, falsches `aud` → 401; gültig → `sid_hash` → rot → `bff.py` → grün · Commit
- [x] **5. Claim-Mapping** — `F01-AC7`
  - [x] Tests: drei Rollen, unbekannte Rolle → 403, mehrere Rollen → Vereinigung, Zitadel-Objektform → rot → grün · Commit
- [x] **6. Endpunkte `/me`, `/residents`, `/residents/{id}`** — `F01-AC9`, `F01-AC10`, `F01-AC12`
  - [x] Integrationstests: WB1 sieht WB1; WB2 bekommt 404 für WB1-ID und für Zufalls-ID (identische Antwort); PDL sieht beide; ohne BFF-Nachweis 401 → rot → grün · Commit `feat(api): add principal-scoped resident endpoints`
- [x] **7. Demo-Nutzer als Code** — `F01-AC16`, `F01-AC17`, `F01-AC18`
  - [x] `infra/demo-users.json`; Test: Setup-Skript erzeugt aus der Datei die erwarteten API-Aufrufe (Attrappe), keine Admin-Rollen → rot → `infra/zitadel/setup.py` → grün
  - [x] Bewerber führt das Skript aus (geführt); Workflow `demo-passwords.yml` (nötig laut S4); Spike-Nutzer `spike-wb1` löschen · Commit `feat(infra): define demo users and roles as code` (26.10.2026: Setup gelaufen, Workflow-Lauf 40355593552 grün, Echt-Token pflege-wb1 → nurse [wb1] von API akzeptiert)
- [x] **8. Sitzung serverseitig** — `F01-AC3`, `F01-AC21`
  - [x] Vitest: Verschlüsselung Roundtrip, Manipulation erkannt, nur Hash gespeichert, Ablauf, Widerruf, paralleler Refresh nur einmal → rot → `session-store.ts`, `session.ts` → grün · Commit (S3 bestanden 27.10.2026)
- [x] **9. BFF-Login, CSRF** — `F01-AC1`, `F01-AC4`, `F01-AC5`, `F01-AC15`, `F01-AC19`
  - [x] Playwright (Test-OIDC-Server): Login WB1 → Cookie-Attribute; kein Token-Muster in HTML, `document.cookie`, Storage, Antworten und Redirect-URLs (auch beim Logout); manipulierter `state` und zweiter Callback → Fehlerseite; POST ohne/mit fremdem `Origin` → 403 → rot
  - [x] Route-Handler + `proxy.ts` → grün · Commit `feat(web): add server-side OIDC login with session store` (S3 aus Vercel: bestanden 27.10.2026)
- [x] **10. Rollenwechsel & Kein Zugriff** — `F01-AC2`, `F01-AC12`, `F01-AC13`, `F01-AC14`, `F01-AC20`
  - [x] Vitest: Rollenknöpfe mit Zugangsdaten + Kopieren; Kopfzeile zeigt Rolle → rot → grün
  - [x] Playwright: WB1 anmelden, Bewohnerliste merken → Rolle WB2 → keine WB1-Namen; Zurück-Taste zeigt keine WB1-Daten; alte Sitzungs-ID wird von BFF abgelehnt; `Cache-Control: no-store`; WB1-Bewohner-URL als WB2 → Bildschirm 8 → rot → grün
  - [x] Commit `feat(web): add role switching and no-access screen` (zusätzlich AC21-Hinweis; E2E startet die API mit)
- [x] **11. CI** — Jobs `db` (supabase start) und `e2e` (Test-OIDC-Server) grün · Commit `ci: run RLS and auth end-to-end tests` (26.10.2026: Lauf 40380223633, alle vier Jobs grün)
- [x] **12. Zugangsdaten nicht mehr öffentlich** — `F01-AC2`, `F01-AC18`, `F01-AC22` · pytest (`setup.py`: Passwörter nur aus Umgebung, Abbruch bei fehlend/kurz/altem Passwort, vor jedem Schreibzugriff; Keycloak-Realm aus `local_password`) · Vitest + Playwright (Startseite zeigt Benutzername und Hinweis, kein Passwort) → rot → grün · Workflow `demo-passwords.yml` mit Secrets · README, Projektbeschreibung, Startseite · Commit `feat: keep the demo passwords out of the repository` · Bewerber legt die drei GitHub-Secrets an, **bevor** gepusht wird · erledigt 03.11.2026: API 607 + DB 433, Web 356 + DB 20, E2E 170 grün
