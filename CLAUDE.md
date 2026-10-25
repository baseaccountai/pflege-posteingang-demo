# CLAUDE.md – Arbeitsregeln für „Pflege-Posteingang“

Bewerbungs-Demo für Stelle Nr. 479 (WiMi Web Engineering, Hochschule Anhalt, Projekt KLARA).
Sichere KI für Pflegedokumente: OIDC, RLS, RAG, Agenten-Autorisierung, Pseudonymisierung, Prompt-Injection-Schutz.

## Immer zuerst lesen

1. Design (Was und Warum): `docs/superpowers/specs/2026-10-23-pflege-posteingang-demo-design.md`
2. Umsetzungsplan (Phasen 0–9): `docs/superpowers/plans/2026-10-23-pflege-posteingang-demo.md`
3. Architektur: `docs/architecture/architecture.md` + ADRs in `docs/architecture/adr/`
4. Feature-Specs: `docs/specs/Fxx-<name>/{requirements,design,tasks}.md`

## Fristen

- Stufe 1 öffentlich erreichbar: **02.11.2026**
- Bewerbungsfertig: **10.11.2026** (Bewerbungsfrist 11.11.2026)

## Verbindliche Regeln

| Regel | Bedeutung |
|---|---|
| Spec vor Code | Kein Feature-Code ohne vom Bewerber freigegebene Spec (Kiro-Stil, EARS-Kriterien `Fxx-ACn`). |
| TDD | Erst Test, Fehlschlag zeigen, dann Code, dann grün. Jedes Akzeptanzkriterium hat ≥ 1 Test. |
| Halte-Punkt pro Phase | Tests grün (Ausgabe zeigen) → Codex-Review → Befunde bewerten/umsetzen → Zusammenfassung → **Stopp, Bewerber entscheidet**. |
| Nur Musterdaten | Erfundene Personen; nie echte Personendaten; nie Schlüssel im Repo. |
| Tokens nie im Browser | Next.js ist BFF, HttpOnly-Session-Cookie. |
| Zugriff im Namen des Nutzers | Backend greift mit Nutzer-/Agenten-Rechten auf Supabase zu (RLS); Service-Key nur für Seed/Reset. |
| Anbieterwechsel nur per Konfiguration | OCR, LLM, Embeddings, IdP über Env-Variablen umschaltbar. |
| Budget | ca. 10–15 € bis zur Bewerbung; Tagesobergrenze für Mistral-Kosten im Backend. |
| Zeitnot | Zuerst lokalen Betrieb reduzieren, **nie** Sicherheitsfeatures. Vorher Bewerber fragen. |
| Entscheidungen | Kleine selbst treffen und im Phasenbericht nennen; alles, was ändert, *was* gebaut wird, vorher fragen. |

## Feste Texte

- Banner auf jedem Bildschirm: `MUSTERDATEN · keine echten Personen`
- Upload-Hinweis: `Bitte keine echten Personendaten hochladen.`
- Footer: `Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt` (keine Logos der Hochschule)

## Sprache

- Kommunikation mit dem Bewerber, Oberfläche, Doku: **Deutsch** (gern Tabellen).
- Code, Bezeichner, Commit-Messages: **Englisch** (Conventional Commits).
- Python-Code bewusst lesbar und kommentiert – der Bewerber muss ihn im Gespräch erklären können.

## Befehle

| Zweck | Befehl |
|---|---|
| Unit-Tests (API + Web) | `make test` |
| End-to-End (Playwright) | `make e2e` |
| Alles per Docker starten | `make up` |
| API-Tests direkt | `cd apps/api && uv run pytest -v` |
| Web-Tests direkt | `cd apps/web && pnpm test` |

## Struktur

`apps/web` (Next.js, Tailwind, shadcn/ui, PWA) · `apps/api` (FastAPI, uv) · `supabase/` (Migrationen, Seed) ·
`samples/` (Musterdokumente) · `infra/` (Docker Compose, Keycloak) · `docs/` (Architektur, Specs, Sicherheit).
