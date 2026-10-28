# F11 – Betrieb & PWA: Design

## PWA

| Teil | Umsetzung |
|---|---|
| Manifest | `apps/web/src/app/manifest.ts` (Next.js Metadata-Route) |
| Icons | `apps/web/public/icons/` (192, 512, maskable), schlichtes Briefkasten-Symbol in Petrol, kein Hochschul-Logo |
| Service Worker | **eigener, minimaler** `apps/web/public/sw.js` (ca. 60 Zeilen) statt Serwist: Next 16 baut standardmäßig mit Turbopack, und der Umfang (Precache + Offline-Seite) rechtfertigt keine Build-Integration. *(Umsetzung 28.10.2026: keine Precache-Liste aus dem Build; nur `offline.html` wird vorab geladen, Allowlist-Dateien beim ersten Abruf.)* [ADR 0008](../../architecture/adr/0008-minimal-service-worker.md). |
| Cache-Regeln | `fetch`-Handler: Pfad in Allowlist (`/_next/static/`, `/icons/`, `/offline.html`) → Cache-first; Navigationsanfrage ohne Netz → `/offline.html`; alles andere: **kein** `respondWith` (Browser-Standard, nichts gespeichert) |
| Offline-Seite | `apps/web/public/offline.html`: statisches HTML ohne Skripte, eigenes Stylesheet, Banner und Footer als Text |
| Navigation | `components/app-nav.tsx`: unten fix (< 768 px), Seitenleiste (≥ 768 px); aktive Route hervorgehoben; Icons aus `lucide-react` |

## Sicherheitsheader

- `apps/web/src/proxy.ts` (Next 16 „Proxy“, früher Middleware) erzeugt pro Anfrage eine Nonce und setzt die CSP: `default-src 'self'; script-src 'self' 'nonce-…' 'strict-dynamic'; style-src 'self' 'nonce-…'; img-src 'self' blob: data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self' <OIDC_ISSUER>`. Alle App-Seiten werden dadurch pro Anfrage gerendert. *(Umsetzung 28.10.2026: `cacheComponents`/Partial Prerendering dafür abgeschaltet – vorgerenderte Seitenhüllen können keine Nonce tragen, Next.js-Leitfaden „Content Security Policy“; die CSP gilt nicht für `/api/*` – keine HTML-Seiten, das Original-PDF soll im Browser-Viewer laufen – und nicht für statische Dateien mit eigenen Headern.)*
- Statische Dateien (`offline.html`, Icons) erhalten über `next.config.ts` `headers()` eine feste CSP ohne Skripte.
- Übrige Header für alle Pfade in `next.config.ts`.
- API: `CORSMiddleware` ohne erlaubte Origins.

## Lokal (Docker Compose)

| Dienst | Quelle | Start |
|---|---|---|
| Supabase | `supabase start` (CLI, eigene Container) | `make up` ruft es vor Compose auf |
| `web`, `api` | vorhandene Dockerfiles | `make up` |
| `oidc-mock` | `ghcr.io/navikt/mock-oauth2-server`, Konfiguration `infra/oidc-mock/config.json` (gleiche Rollen-Claims) | `make up-test` (Profil `test`) |
| `keycloak`, `ollama`, `docling` | Phase 8 | – |

## CI/CD

| Workflow | Auslöser | Jobs |
|---|---|---|
| `ci.yml` (vorhanden, erweitert) | push, PR | `api` (ruff, pytest unit), `db` (supabase start, Migrationen, DB- und Integrationstests), `web` (lint, vitest, playwright mit `oidc-mock`), `secrets` (gitleaks) |
| `deploy.yml` | `workflow_run` von CI, `conclusion == success`, Branch `main`; `concurrency: deploy` (keine Parallelität, nicht abbrechen) | checkout **`github.event.workflow_run.head_sha`** → `migrate` (`supabase db push`) → `api` (Vercel-Projekt der API: `vercel pull` / `vercel build --prod` / `vercel deploy --prebuilt --prod`, danach `/health` abwarten; Deployment trägt die SHA als Metadatum, [ADR 0011](../../architecture/adr/0011-api-on-vercel.md)) → `web` (`vercel pull` / `vercel build --prod` / `vercel deploy --prebuilt --prod`); `needs` verkettet, Abbruch beim ersten Fehler |
| Vercel-Git-Integration | nur Vorschau | `apps/web/vercel.json` und `apps/api/vercel.json`: `git.deploymentEnabled.main = false` |

Die Prüfung „kaputte Migration stoppt das API-Deployment“ wird einmalig auf einem Wegwerf-Branch mit `workflow_dispatch` vorgeführt.

## Konfiguration

Zentrale Übersicht aller Variablen mit Dienst, Pflicht, Standardwert und Geheimhaltung: [../konfiguration.md](../konfiguration.md).

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Web | Vitest | AC1 (Manifest-Felder), AC4 (Navigation: vier Einträge in Reihenfolge), Allowlist-Funktion des SW (Tabellentest mit allen ausgeschlossenen Pfadarten) |
| End-to-End | Playwright (Produktionsbuild) | AC2 (nach Login, Upload, Akte und Frage: alle Schlüssel im Cache Storage passen zur Allowlist), AC3 (offline → Offline-Seite), AC4 (mobile unten, desktop Seitenleiste), AC11 (Header vorhanden; `securitypolicyviolation`-Ereignisse = 0 auf allen Seitentypen) |
| Integration API | pytest | AC12 (CORS-Preflight fremder Origin abgelehnt; gültiges Token ohne BFF-Nachweis → 401) |
| CI | GitHub Actions | AC6, AC8 (Wegwerf-Branch), AC10 (gitleaks erkennt Test-Schlüssel im Wegwerf-Branch) |
| Abnahme Deployment | GitHub Actions + Ausgaben | AC7: Migration, API- und Web-Deployment nennen dieselbe SHA (Workflow-Zusammenfassung prüft das automatisch); zwei schnell aufeinanderfolgende Pushes → zweiter Deploy wartet; AC9: Push auf `main` erzeugt in Vercel **kein** Git-Produktionsdeployment, nur das des Workflows; Region `fra1` im `x-vercel-id` einer Funktionsantwort |
| Manuell (Abnahme) | Handy (Android/iOS) | AC1 Installation, API `/health/ready` auf Vercel |
