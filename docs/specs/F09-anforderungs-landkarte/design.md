# F09 – Anforderungs-Landkarte: Design

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Daten | `apps/web/src/content/requirements-map.ts` | `RequirementEntry { id, text, level: "gefordert" \| "wuenschenswert", how, appHref?, repoPath, status: "live" \| "stufe2" }` |
| Karte | `components/requirements-map.tsx` | Liste (Handy) / Raster (Desktop), Badges |
| Projektkarte | `components/project-card.tsx` | oberste Karte mit Link `/projekt` |
| Kopfzeile | `components/site-header.tsx` | App-Name, Link „Über das Projekt“, Rolle + Abmelden (F01-AC16) |
| Startseite | `app/page.tsx` | Projektkarte → Landkarte → Rollenwechsel; ohne API-Abfrage (pro Anfrage gerendert wegen CSP-Nonce, F11) |
| Platzhalter | `app/projekt/page.tsx` | Phase-9-Platzhalter |

Repo-Links werden aus `NEXT_PUBLIC_REPO_URL` + `repoPath` gebildet (Repo ist zunächst privat; ab Veröffentlichung funktionieren die Links für alle).

## Einträge (aus Design 1)

| Anforderung | Stufe | App | Repo |
|---|---|---|---|
| Softwarearchitektur, Web-Backend (Python/TypeScript) | gefordert | – | `docs/architecture/`, `apps/api/`, `apps/web/` |
| Anbindung von LLMs über APIs | gefordert | `/posteingang` | `apps/api/app/providers/` |
| RAG, agentenbasierte KI | gefordert | `/fragen` (Agent: Stufe 2) | `apps/api/app/rag/` |
| IT-/API-Sicherheit, OAuth 2.0/OIDC | gefordert | Rollenwechsel, `/bewohner` | `apps/api/app/auth/`, `supabase/migrations/` |
| Lokale Modelle | wünschenswert | – | `infra/` (Phase 8) |
| Docker, CI/CD | wünschenswert | – | `infra/docker-compose.yml`, `.github/workflows/` |
| Sicherheitsrisiken von LLM-Anwendungen | wünschenswert | Stufe 2 | `docs/security/threat-model.md` |

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Web | Vitest | AC3 (alle Einträge gerendert, Badges), AC4, AC5 (jeder `appHref` existiert als Route – Test liest `src/app/**/page.tsx`) |
| End-to-End | Playwright (desktop + mobile) | AC1 (Reihenfolge: Projektkarte vor Landkarte), AC2 (Kopfzeile auf `/`, `/bewohner`, `/fragen`, `/posteingang`), AC6, AC7 (API gestoppt → Startseite vollständig), AC8 |
