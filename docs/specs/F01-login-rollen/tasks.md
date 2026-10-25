# F01 – Login & Rollen: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [ ] **1. Spike S1 + S3: Datenbank im Namen des Nutzers** — `F01-AC9`, `F01-AC10`, `F01-AC11`
  - [ ] Migration `f01_auth` (Schema `app`, `wards`, `residents`, Rollen, `bff.sessions`, `revoke … from anon`)
  - [ ] `tests/rls/test_ward_isolation.py`: ohne Filter; WB1-Fehler→Rollback→WB2 auf derselben Verbindung; 20 parallele Anfragen gemischt; ohne Claims → 0 Zeilen und Schreibfehler → rot → `db.as_principal()` → grün
  - [ ] Dieselben Tests gegen Cloud-Supabase über den Pooler (manuell, Ergebnis notieren); BFF-Rolle von einer Vercel-Preview-Funktion
  - [ ] ADR 0007 „Datenbankzugriff im Namen des Nutzers“; **Halt, falls S1 scheitert** (Bewerber informieren)
  - [ ] Commit: `feat(db): add ward isolation with RLS (spike F01)`
- [ ] **2. Spike S2 + S4: Zitadel** — Setup-Skript-Entwurf, Token holen, Claims/`aud`/Typ prüfen, Passwortänderung als Demo-Nutzer versuchen; Ergebnis in ADR 0007 · Commit
- [ ] **3. Token-Prüfung** — `F01-AC6`, `F01-AC19`
  - [ ] `tests/auth/test_tokens.py`: gültig, abgelaufen, `nbf` in Zukunft, falscher `iss`, falscher `aud`, `alg=none`, `HS256` mit Public Key, unbekannter `kid` → rot → `tokens.py` → grün · Commit `feat(api): verify OIDC access tokens via JWKS`
- [ ] **4. BFF-Nachweis** — `F01-AC8`
  - [ ] Tests: fehlt, abgelaufen, falsche Signatur, falsches `aud` → 401; gültig → `sid_hash` → rot → `bff.py` → grün · Commit
- [ ] **5. Claim-Mapping** — `F01-AC7`
  - [ ] Tests: drei Rollen, unbekannte Rolle → 403, mehrere Rollen → Vereinigung, Zitadel-Objektform → rot → grün · Commit
- [ ] **6. Endpunkte `/me`, `/residents`, `/residents/{id}`** — `F01-AC9`, `F01-AC10`, `F01-AC12`
  - [ ] Integrationstests: WB1 sieht WB1; WB2 bekommt 404 für WB1-ID und für Zufalls-ID (identische Antwort); PDL sieht beide; ohne BFF-Nachweis 401 → rot → grün · Commit `feat(api): add principal-scoped resident endpoints`
- [ ] **7. Demo-Nutzer als Code** — `F01-AC16`, `F01-AC17`, `F01-AC18`
  - [ ] `infra/demo-users.json`; Test: Setup-Skript erzeugt aus der Datei die erwarteten API-Aufrufe (Attrappe), keine Admin-Rollen → rot → `infra/zitadel/setup.py` → grün
  - [ ] Bewerber führt das Skript aus (geführt); ggf. Workflow `demo-passwords.yml` · Commit `feat(infra): define demo users and roles as code`
- [ ] **8. Sitzung serverseitig** — `F01-AC3`, `F01-AC21`
  - [ ] Vitest: Verschlüsselung Roundtrip, Manipulation erkannt, nur Hash gespeichert, Ablauf, Widerruf, paralleler Refresh nur einmal → rot → `session-store.ts`, `session.ts` → grün · Commit
- [ ] **9. BFF-Login, CSRF** — `F01-AC1`, `F01-AC4`, `F01-AC5`, `F01-AC15`, `F01-AC19`
  - [ ] Playwright (Test-OIDC-Server): Login WB1 → Cookie-Attribute; kein Token-Muster in HTML, `document.cookie`, Storage, Antworten; manipulierter `state` und zweiter Callback → Fehlerseite; POST ohne/mit fremdem `Origin` → 403 → rot
  - [ ] Route-Handler + `proxy.ts` → grün · Commit `feat(web): add server-side OIDC login with session store`
- [ ] **10. Rollenwechsel & Kein Zugriff** — `F01-AC2`, `F01-AC12`, `F01-AC13`, `F01-AC14`, `F01-AC20`
  - [ ] Vitest: Rollenknöpfe mit Zugangsdaten + Kopieren; Kopfzeile zeigt Rolle → rot → grün
  - [ ] Playwright: WB1 anmelden, Bewohnerliste merken → Rolle WB2 → keine WB1-Namen; Zurück-Taste zeigt keine WB1-Daten; alte Sitzungs-ID wird von BFF abgelehnt; `Cache-Control: no-store`; WB1-Bewohner-URL als WB2 → Bildschirm 8 → rot → grün
  - [ ] Commit `feat(web): add role switching and no-access screen`
- [ ] **11. CI** — Jobs `db` (supabase start) und `e2e` (Test-OIDC-Server) grün · Commit `ci: run RLS and auth end-to-end tests`
