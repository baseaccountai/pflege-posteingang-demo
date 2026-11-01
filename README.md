# Pflege-Posteingang

> Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt.
> **Alle Personen und Dokumente sind erfundene Musterdaten.**

**Demo:** <https://pflege-posteingang-demo.vercel.app> · **Projektbeschreibung:** [`docs/projektbeschreibung.md`](docs/projektbeschreibung.md) (auch in der App unter „Über das Projekt“)

Digitaler Posteingang einer Pflegeeinrichtung mit generativer KI und sichtbarer Sicherheitsarchitektur:
Papierdokumente werden per OCR erfasst, die KI schlägt Felder vor, **ein Mensch gibt frei**. Pflegekräfte
stellen Fragen an die Dokumente (RAG) und erhalten Antworten mit Quellen. Ein Agent schlägt Wiedervorlagen
vor, gespeichert wird erst nach Bestätigung.

| Sicherheitsbaustein | Umsetzung |
|---|---|
| Login und Rollen | OIDC (Zitadel) über Next.js als Backend-for-Frontend, Tokens nie im Browser |
| Rechte | Row Level Security je Wohnbereich; die API greift im Namen des Nutzers zu |
| Agent | eigenes Token per Token Exchange (RFC 8693), fünf Werkzeuge, Schreiben nur nach Bestätigung |
| Datenschutz | Pseudonymisierung vor jedem Sprachmodell; ein Modell-Tor verweigert Aufrufe mit Klarnamen |
| Prompt-Injection | fünf Schichten; gemessen 89,6 % Erkennung bei 11,3 % Fehlalarm ([Bericht](docs/security/reports/2026-10-31-injection.md)) |

| Bereich | Technik |
|---|---|
| Web-App | Next.js, Tailwind, shadcn/ui, PWA |
| Backend | Python, FastAPI |
| Daten | Supabase (Postgres, pgvector, RLS) |
| Login | Zitadel (öffentlich) / Keycloak (lokal) |
| KI | Mistral (öffentlich) / Ollama + Docling (lokal) |

## Schnellstart lokal

Voraussetzungen: Python ≥ 3.12 mit [uv](https://docs.astral.sh/uv/), Node 22 mit pnpm, Docker (ohne Compose-Plugin), make.

```bash
make setup  # einmalig: Abhängigkeiten + Playwright-Browser
make test   # Unit-Tests API + Web
make e2e    # End-to-End (Desktop + Handy)
make up-test  # ohne Konto/Schlüssel: Supabase + Web + API + Test-IdP, Attrappen für OCR/LLM
make smoke    # prüft Startseite, API mit Datenbank und Test-IdP
make up       # wie oben, aber echte Anbieter und IdP aus .env
make down
```

Lokal laufen Web (http://localhost:3000) und API (http://localhost:8000) per `docker run` im Host-Netzwerk (`infra/local-stack.sh`); Supabase kommt über die CLI (`make db-start`). Im Test-IdP (http://localhost:18090/default) meldet man sich mit beliebigem Namen an und trägt die Rolle als Claims ein, z. B. `{"roles": ["nurse_wb1"]}` (Rollen: `nurse_wb1`, `nurse_wb2`, `pdl`).

## Dokumentation

- Architektur: [`docs/architecture/architecture.md`](docs/architecture/architecture.md)
- Feature-Specs: [`docs/specs/`](docs/specs/)
- Bedrohungsmodell: [`docs/security/threat-model.md`](docs/security/threat-model.md)
- Projektbeschreibung: [`docs/projektbeschreibung.md`](docs/projektbeschreibung.md) – Text ändern, dann `make project-description` (kopiert ihn in die App); Bilder neu mit `make screens`
