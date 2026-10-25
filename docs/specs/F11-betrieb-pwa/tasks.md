# F11 – Betrieb & PWA: Aufgaben

- [ ] **1. Navigation** — `F11-AC4` · Vitest + Playwright (mobile unten, desktop Seite) → rot → `app-nav.tsx` → grün · Commit
- [ ] **2. Manifest + Icons** — `F11-AC1` · Vitest → rot → grün · Commit `feat(web): add web app manifest`
- [ ] **3. Service Worker + Offline-Seite (ADR 0008)** — `F11-AC2`, `F11-AC3` · Vitest (Allowlist) + Playwright (Cache-Inhalt nach typischem Ablauf, offline) → rot → `sw.js`, `offline.html`, `sw-manifest.mjs` → grün · Commit `feat(web): add allowlist-only service worker`
- [ ] **4. Sicherheitsheader + CSP-Nonce + CORS** — `F11-AC11`, `F11-AC12` · Playwright (Header, 0 CSP-Verletzungen auf allen Seitentypen) + pytest → rot → `proxy.ts`, `next.config.ts`, API-Middleware → grün · Commit
- [ ] **5. Lokal: `make up`, `make up-test`, Test-OIDC-Server** — `F11-AC5` · Smoke-Skript `infra/smoke.sh` (Startseite, `/health/ready`, OIDC-Discovery des Mocks) → rot → grün · Commit
- [ ] **6. CI erweitern** — `F11-AC6`, `F11-AC10` · Jobs `db`, `secrets`, E2E mit Mock; Wegwerf-Branch mit Test-Schlüssel wird erkannt · Commit `ci: add database, e2e and secret scanning jobs`
- [ ] **7. Koyeb + Deploy-Workflow** — `F11-AC7`, `F11-AC8`, `F11-AC9` · Bewerber legt Koyeb-Konto an (geführt) und hinterlegt Secrets; `deploy.yml`; `vercel.json` (Git-Deploy für `main` aus); Wegwerf-Branch mit kaputter Migration stoppt API- und Web-Schritt; SHA-Gleichheitsprüfung im Workflow; Serialisierung mit zwei Pushes; kein Vercel-Git-Produktionsdeployment · Commit `ci: deploy migrations, api and web for the same green commit`
- [ ] **8. Abnahme öffentlich** — Handy-Installation, Region, Koyeb-Health; Ergebnisse im Phasenbericht
