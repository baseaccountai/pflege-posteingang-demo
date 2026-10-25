# F01 – Login & Rollen: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [ ] **1. Spike S1–S3** — klärt Risiko aus Design 10
  - [ ] Migration mit `wards`, `residents`, `app.*`-Funktionen, Policy, Rolle `api_gateway`
  - [ ] Test `apps/api/tests/rls/test_ward_isolation.py::test_wb2_sees_no_wb1_rows` (lokales Supabase) → rot → `db.as_principal()` → grün
  - [ ] Derselbe Test gegen Cloud-Supabase über den Pooler (manuell, Ergebnis notieren)
  - [ ] Zitadel-Token manuell holen, Claims prüfen (JWT? Rollen? `aud`?)
  - [ ] Token Exchange in Zitadel (Feature-Flag) und Keycloak prüfen
  - [ ] ADR 0007 „Datenbankzugriff im Namen des Nutzers“ schreiben; **Halt, falls S1 scheitert** (Bewerber informieren)
  - [ ] Commit: `feat(db): add ward isolation with RLS (spike F01)`
- [ ] **2. Token-Prüfung** — `F01-AC6`, `F01-AC15`
  - [ ] Tests `tests/auth/test_tokens.py`: gültig, abgelaufen, falscher `iss`, falscher `aud`, `alg=none`, `HS256` mit Public Key, unbekannter `kid` → rot
  - [ ] `app/auth/tokens.py` → grün · Commit `feat(api): verify OIDC access tokens via JWKS`
- [ ] **3. Claim-Mapping** — `F01-AC7`
  - [ ] Tests `tests/auth/test_claims.py`: drei Rollen, unbekannte Rolle → 403, mehrere Rollen → Vereinigung → rot
  - [ ] `app/auth/claims.py` → grün · Commit `feat(api): derive ward permissions from role claims`
- [ ] **4. `/me`, `/residents`, `/residents/{id}`** — `F01-AC8`, `F01-AC9`, `F01-AC10`
  - [ ] Integrationstests: WB1 sieht WB1; WB2 bekommt 404 für WB1-ID und für Zufalls-ID (gleiche Antwort); PDL sieht beide → rot
  - [ ] Endpunkte über `as_principal()` → grün · Commit `feat(api): add principal-scoped resident endpoints`
- [ ] **5. IdP als Code** — `F01-AC13`, `F01-AC14`
  - [ ] `infra/keycloak/realm-pflege.json` + Compose-Dienst `keycloak` (Profil `auth`)
  - [ ] `infra/zitadel/setup.py` (idempotent) + Anleitung im README; Bewerber führt es aus
  - [ ] Test `tests/auth/test_realm_parity.py`: Realm-Datei und Zitadel-Setup definieren dieselben Nutzer/Rollen (aus gemeinsamer `infra/demo-users.json`) → rot → grün
  - [ ] Commit `feat(infra): define demo users and roles as code`
- [ ] **6. BFF-Login** — `F01-AC1`, `F01-AC3`, `F01-AC4`, `F01-AC5`, `F01-AC17`
  - [ ] Vitest: Session-Verschlüsselung (Roundtrip, Manipulation erkannt, Ablauf) → rot → `session.ts` → grün
  - [ ] Playwright (Keycloak lokal): Login WB1 → Cookie-Attribute prüfen; kein Token-Muster (`eyJ`) in HTML, Storage, `document.cookie`; manipulierter `state` → Fehlerseite → rot
  - [ ] Route-Handler → grün · Commit `feat(web): add server-side OIDC login with encrypted session`
- [ ] **7. Rollenwechsel & Kein Zugriff** — `F01-AC2`, `F01-AC10`, `F01-AC11`, `F01-AC12`, `F01-AC16`
  - [ ] Vitest: Rollenknöpfe zeigen Zugangsdaten + Kopieren; Kopfzeile zeigt Rolle → rot → grün
  - [ ] Playwright: WB1 anmelden, Bewohnerliste merken → Rolle WB2 → Liste ohne WB1-Namen; Zurück-Taste zeigt keine WB1-Daten; `Cache-Control: no-store`; WB1-Bewohner-URL als WB2 → Bildschirm 8 → rot → grün
  - [ ] Commit `feat(web): add role switching and no-access screen`
- [ ] **8. CI** — Jobs `rls` (supabase start) und `e2e-auth` (Keycloak) grün · Commit `ci: run RLS and auth end-to-end tests`
