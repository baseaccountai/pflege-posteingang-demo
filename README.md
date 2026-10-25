# Pflege-Posteingang

> **In Arbeit.** Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt.

Digitaler Posteingang einer Pflegeeinrichtung mit sicherer KI: Papierdokumente (Arztbrief, Medikationsplan,
Überleitungsbogen) werden per OCR erfasst, KI schlägt strukturierte Felder vor, ein Mensch gibt frei.
Pflegekräfte stellen Fragen an die Dokumente (RAG) und erhalten Antworten mit Quellen.

Sichtbare Sicherheitsarchitektur: OIDC-Login, Row Level Security pro Wohnbereich, eingeschränkte Agenten-Rechte,
Pseudonymisierung vor dem LLM, Prompt-Injection-Erkennung.

**Alle Daten sind erfundene Musterdaten.**

| Bereich | Technik |
|---|---|
| Web-App | Next.js, Tailwind, shadcn/ui, PWA |
| Backend | Python, FastAPI |
| Daten | Supabase (Postgres, pgvector, RLS) |
| Login | Zitadel (öffentlich) / Keycloak (lokal) |
| KI | Mistral (öffentlich) / Ollama + Docling (lokal) |

## Schnellstart lokal

```bash
make test   # Unit-Tests API + Web
make up     # Web (http://localhost:3000) + API (http://localhost:8000)
```

## Dokumentation

- Architektur: [`docs/architecture/architecture.md`](docs/architecture/architecture.md)
- Feature-Specs: [`docs/specs/`](docs/specs/)
- Bedrohungsmodell: [`docs/security/threat-model.md`](docs/security/threat-model.md)
