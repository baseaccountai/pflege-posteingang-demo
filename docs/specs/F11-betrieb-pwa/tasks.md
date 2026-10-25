# F11 – Betrieb & PWA: Aufgaben

- [ ] **1. Navigation** — `F11-AC4` · Vitest + Playwright (mobile unten, desktop Seite) → rot → `app-nav.tsx` → grün · Commit
- [ ] **2. Manifest + Icons** — `F11-AC1` · Vitest → rot → grün · Commit `feat(web): add web app manifest`
- [ ] **3. Spike Service Worker (ADR 0008)** + Umsetzung — `F11-AC2`, `F11-AC3` · Playwright (Cache-Inhalt, offline) → rot → grün · Commit `feat(web): add offline-safe service worker`
- [ ] **4. Sicherheitsheader + CORS** — `F11-AC11`, `F11-AC12` · Playwright/pytest → rot → grün · Commit
- [ ] **5. Compose: Keycloak + Supabase-Start in `make up`** — `F11-AC5` · Smoke-Test-Skript `infra/smoke.sh` (Login-Seite, `/health/ready`) → rot → grün · Commit
- [ ] **6. CI erweitern** — `F11-AC6`, `F11-AC10` · Jobs `db`, `secrets`; absichtlich eingecheckter Test-Schlüssel in einem Wegwerf-Branch wird erkannt → Commit `ci: add database and secret scanning jobs`
- [ ] **7. Koyeb + Deploy-Workflow** — `F11-AC7`, `F11-AC9` · Bewerber legt Koyeb-Konto an (geführt); Workflow; Test: kaputte Migration im Wegwerf-Branch stoppt API-Deploy · Commit `ci: deploy migrations and api on green main`
- [ ] **8. Vercel-Produktionsregel** — `F11-AC8` · Region prüfen (Funktions-Antwort-Header), „Ignored Build Step“ gemäß Freigabe · Commit
