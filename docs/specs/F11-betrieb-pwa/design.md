# F11 – Betrieb & PWA: Design

## PWA

| Teil | Umsetzung |
|---|---|
| Manifest | `apps/web/src/app/manifest.ts` (Next.js Metadata-Route) |
| Icons | `apps/web/public/icons/` (192, 512, maskable), schlichtes Briefkasten-Symbol in Petrol, kein Hochschul-Logo |
| Service Worker | Serwist; **Spike:** Next 16 baut mit Turbopack – Serwist-Variante für Turbopack prüfen, sonst `next build --webpack` nur für den SW-Build oder handgeschriebener minimaler SW (`public/sw.js`, nur Precache + Offline-Seite). Entscheidung als ADR 0008. |
| Cache-Regeln | Precache: Build-Assets, `/offline`; Laufzeit: `NetworkOnly` für alles Übrige |
| Navigation | `components/app-nav.tsx`: unten fix (< 768 px), Seitenleiste (≥ 768 px); aktive Route hervorgehoben; Icons aus `lucide-react` |

## Lokal (Docker Compose)

| Dienst | Quelle | Profil |
|---|---|---|
| `web`, `api` | vorhandene Dockerfiles | Standard |
| Supabase | `supabase start` (CLI, eigene Container) – `make up` ruft es vor `docker compose up` auf | Standard |
| `keycloak` | `quay.io/keycloak/keycloak` mit Realm-Import (F01) | Standard |
| `ollama`, `docling` | Phase 8 | `local-llm` |

Voraussetzung lokal: Docker mit Compose-Plugin.

## CI/CD

| Workflow | Auslöser | Jobs |
|---|---|---|
| `ci.yml` (vorhanden, erweitert) | push, PR | `api` (ruff, pytest unit), `db` (supabase start, Migrationen, RLS- und Integrationstests), `web` (lint, vitest, playwright), `secrets` (gitleaks) |
| `deploy.yml` | `workflow_run` von CI auf `main` mit Erfolg | `migrate` (`supabase db push` mit `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`) → `api` (Koyeb: Image bauen, in GHCR pushen, `koyeb service update` mit neuem Image) |
| Vercel | Git-Integration | Preview je Push, Produktion von `main` |

**Abweichung vom Plan, zur Freigabe:** Das Web wird über die Vercel-Git-Integration statt per GitHub Action ausgerollt (bereits eingerichtet, Previews pro Push gratis). Konsequenz: Ein Web-Deployment kann vor einer grünen CI live gehen. Gegenmaßnahme: In Vercel „Ignored Build Step“ so setzen, dass Produktion nur baut, wenn der Commit-Status der CI grün ist – oder Akzeptanz, da Web keine Daten hält.

## Konfiguration (Variablen, ohne Werte in `.env.example`)

`LLM_PROVIDER`, `OCR_PROVIDER`, `MISTRAL_API_KEY`, `MISTRAL_CHAT_MODEL`, `MISTRAL_OCR_MODEL`, `MISTRAL_EMBED_MODEL`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_AUDIENCE`, `OIDC_ROLES_CLAIM`, `SESSION_SECRET`, `API_BASE_URL`, `DATABASE_URL` (Rolle `api_gateway`), `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY` (nur Reset), `DAILY_OCR_PAGE_LIMIT`, `DAILY_LLM_CALL_LIMIT`, `SESSION_UPLOAD_LIMIT`, `NEXT_PUBLIC_REPO_URL`.

## Sicherheitsheader

In `apps/web/next.config.ts` (`headers()`); CSP mit Nonce für Next-Inline-Skripte (Middleware/Proxy), `img-src 'self' blob: data:`, `connect-src 'self'`. API: `CORSMiddleware` ohne erlaubte Origins (nur Server-zu-Server).

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Web | Vitest | AC1 (Manifest-Felder), AC4 (Navigation: vier Einträge in Reihenfolge) |
| End-to-End | Playwright | AC2 (nach Login: Cache Storage enthält keine `/bewohner`-/API-Antworten), AC3 (offline → Offline-Seite), AC4 (mobile: unten, desktop: Seitenleiste), AC11 (Header vorhanden) |
| Integration API | pytest | AC12 (CORS-Preflight von fremder Origin abgelehnt) |
| CI | GitHub Actions | AC6, AC9 (Deploy hängt an `migrate`), AC10 (gitleaks-Job) |
| Manuell (Abnahme) | Handy (Android/iOS) | AC1 Installation, AC8 Region, AC7 Koyeb erreichbar |
