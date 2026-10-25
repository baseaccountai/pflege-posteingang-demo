# F11 – Docker Compose lokal, CI/CD, Deployment, PWA: Anforderungen

Status: Entwurf · Stufe: 1 (lokaler Vollbetrieb mit Ollama/Docling: Phase 8) · Bildschirme: alle

## Einführung

Die Demo läuft öffentlich (Vercel + Koyeb Frankfurt + Supabase + Zitadel) und lokal per Docker Compose; Tests und Deployment laufen über GitHub Actions. Auf dem Handy ist sie als PWA installierbar. Grundlage: Design 3, 4, 5.1, 6 (untere Navigation), 9.

## User Stories

- **US-1:** Als Professor möchte ich die Demo auf dem Handy wie eine App öffnen können.
- **US-2:** Als Entwickler möchte ich mit einem Befehl alles lokal starten.
- **US-3:** Als Bewerber möchte ich, dass jeder Push auf `main` getestet und nur bei grünen Tests veröffentlicht wird.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F11-AC1 | Das System soll ein Web-App-Manifest bereitstellen (Name „Pflege-Posteingang“, Kurzname, `display: standalone`, Theme-Farbe Petrol, Icons 192/512 px inkl. `maskable`), sodass Chrome/Android und Safari/iOS die Installation anbieten. |
| F11-AC2 | Das System soll einen Service Worker (Serwist) registrieren, der **nur statische Assets** (JS, CSS, Schriften, Icons) und eine Offline-Seite cached; Antworten mit Nutzerdaten, `/auth/*` und API-Aufrufe werden nie gecached. |
| F11-AC3 | WENN keine Verbindung besteht, DANN soll das System die Offline-Seite „Keine Verbindung – die Demo braucht Internet“ zeigen. |
| F11-AC4 | Das System soll auf Handy-Breite eine untere Navigation „Start · Posteingang · Bewohner · Fragen“ zeigen und auf Tablet/Desktop dieselben Bereiche als Seitenleiste bzw. nebeneinander. |
| F11-AC5 | `make up` soll Web, API, lokales Supabase und Keycloak starten; das Profil `local-llm` (Ollama, Docling) wird in Phase 8 ergänzt. |
| F11-AC6 | Die CI soll bei jedem Push und Pull Request ausführen: ruff, pytest (Unit + Integration), RLS-Tests gegen lokales Supabase, ESLint, Vitest, Playwright (desktop + mobile). |
| F11-AC7 | WENN die CI auf `main` grün ist, DANN soll ein Deploy-Workflow die Datenbank-Migrationen auf Supabase anwenden und danach die API auf Koyeb (Region Frankfurt) aus `apps/api/Dockerfile` ausrollen. |
| F11-AC8 | Das Web soll über die Vercel-Git-Integration ausgerollt werden: Produktion nur von `main`, Funktionen in Region `fra1`. |
| F11-AC9 | FALLS die Migration fehlschlägt, DANN soll das API-Deployment nicht starten. |
| F11-AC10 | Alle Geheimnisse sollen nur in den Secret-Stores von GitHub, Vercel und Koyeb bzw. lokal in `.env` liegen; `.env.example` listet alle Variablennamen ohne Werte, und die CI prüft per Secret-Scan (gitleaks), dass keine Schlüssel eingecheckt sind. |
| F11-AC11 | Das System soll HTTP-Sicherheitsheader setzen: `Content-Security-Policy` (ohne `unsafe-eval`), `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (Kamera nur `self`). |
| F11-AC12 | Die API soll nur Anfragen vom BFF annehmen (CORS gesperrt; öffentlich erreichbar, aber jede Fach-Route verlangt ein gültiges Token, F01-AC6). |

## Nicht im Umfang

Ollama/Docling-Container (Phase 8), Supabase self-hosted ohne CLI (Phase 8), Monitoring.
