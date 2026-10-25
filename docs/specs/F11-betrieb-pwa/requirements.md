# F11 – Docker Compose lokal, CI/CD, Deployment, PWA: Anforderungen

Status: Entwurf (überarbeitet nach Codex-Review) · Stufe: 1 (Keycloak, Ollama, Docling: Phase 8) · Bildschirme: alle

## Einführung

Die Demo läuft öffentlich (Vercel + Koyeb Frankfurt + Supabase + Zitadel) und lokal per Docker Compose; Tests und Deployment laufen über **einen** GitHub-Actions-Ablauf, der nur geprüfte Commits veröffentlicht. Auf dem Handy ist sie als PWA installierbar. Grundlage: Design 3, 4, 5.1, 6 (untere Navigation), 9.

## User Stories

- **US-1:** Als Professor möchte ich die Demo auf dem Handy wie eine App öffnen können.
- **US-2:** Als Entwickler möchte ich mit einem Befehl alles lokal starten.
- **US-3:** Als Bewerber möchte ich, dass nur ein vollständig getesteter Commit veröffentlicht wird – Datenbank, API und Web im selben Stand.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F11-AC1 | Das System soll ein Web-App-Manifest bereitstellen (Name „Pflege-Posteingang“, Kurzname, `display: standalone`, Theme-Farbe Petrol, Icons 192/512 px inkl. `maskable`), sodass Chrome/Android und Safari/iOS die Installation anbieten. |
| F11-AC2 | Das System soll einen Service Worker registrieren, der **ausschließlich** Einträge einer festen Liste cached (`/_next/static/*`, `/icons/*`, `/offline.html`); alle anderen Antworten – insbesondere Seiten, RSC-Anfragen, `/auth/*`, `/api/*`, Dokumentdateien und Fragen – gehen immer ans Netz und werden nie gespeichert. |
| F11-AC3 | WENN keine Verbindung besteht und eine Seite aufgerufen wird, DANN soll das System die Offline-Seite „Keine Verbindung – die Demo braucht Internet“ zeigen. |
| F11-AC4 | Das System soll auf Handy-Breite (< 768 px) eine untere Navigation „Start · Posteingang · Bewohner · Fragen“ zeigen und ab 768 px dieselben Bereiche als Seitenleiste. |
| F11-AC5 | `make up` soll lokales Supabase (CLI) sowie Web und API (Compose) starten; `make up-test` zusätzlich den Test-OIDC-Server. Keycloak und das Profil `local-llm` (Ollama, Docling) folgen in Phase 8. |
| F11-AC6 | Die CI soll bei jedem Push und Pull Request ausführen: ruff, pytest (Unit), Datenbank- und Integrationstests gegen lokales Supabase, ESLint, Vitest, Playwright (desktop + mobile) gegen Test-OIDC-Server, Secret-Scan (gitleaks). |
| F11-AC7 | WENN die CI für einen Commit auf `main` vollständig grün ist, DANN soll ein Deploy-Workflow für **genau diesen Commit** nacheinander die Migrationen auf Supabase anwenden, die API auf Koyeb (Frankfurt, Image-Tag = Commit) und das Web auf Vercel (Produktion, Region `fra1`) ausrollen; Deploy-Läufe laufen nie parallel. |
| F11-AC8 | FALLS ein Schritt des Deploy-Workflows fehlschlägt, DANN soll kein späterer Schritt starten. |
| F11-AC9 | Vercel soll Produktions-Deployments nur über den Deploy-Workflow erhalten; automatische Git-Deployments sind für `main` abgeschaltet, Vorschau-Deployments für andere Branches bleiben. |
| F11-AC10 | Alle Geheimnisse sollen nur in den Secret-Stores von GitHub, Vercel und Koyeb bzw. lokal in `.env` liegen; `.env.example` listet alle Variablennamen ohne Werte (Übersicht: [konfiguration.md](../konfiguration.md)). |
| F11-AC11 | Das System soll auf allen Seiten HTTP-Sicherheitsheader setzen: `Content-Security-Policy` mit Nonce pro Anfrage (ohne `unsafe-eval`, ohne `unsafe-inline` für Skripte), `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (Kamera nur `self`); der Produktionsbuild erzeugt dabei keine CSP-Verletzungen. |
| F11-AC12 | Die API soll keine Browser-Origins erlauben (CORS gesperrt) und jede Fach-Route nur mit gültigem Token und BFF-Nachweis beantworten (F01-AC6, F01-AC8). |

## Nicht im Umfang

Keycloak, Ollama/Docling-Container, Supabase self-hosted ohne CLI (Phase 8), Monitoring.
