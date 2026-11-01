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

### Komplett lokal (ohne Cloud)

Login, OCR, Modelle und Datenbank laufen auf dem eigenen Rechner: Keycloak, Docling, Ollama und das lokale Supabase. Es wird keine `.env` gelesen, und kein Text verlässt den Rechner.

```bash
ollama pull qwen3:8b && ollama pull bge-m3   # einmalig; Ollama läuft nativ (ollama serve)
make up-local    # Supabase + Keycloak + Docling + API + Web; setzt die lokalen Musterdaten zurück und indiziert sie mit bge-m3
make smoke-local # prüft alle Dienste und ruft die echten Modelle einmal auf
make down
```

Anmelden wie öffentlich, etwa mit `pflege-wb1` / `Pflege-WB1-Demo!`. Speicherbedarf: etwa 10 GB frei. Gemessen am 01.11.2026 auf einem Laptop ohne GPU (8 Kerne, 15 GB):

| Schritt | Dauer |
|---|---|
| Keycloak-Start | ~75 s |
| Docling liest einen Brief | 12–32 s |
| Upload bis „bereit zur Prüfung“ (OCR, Injection-Prüfung, Feldvorschlag mit `qwen3:8b`) | ~14 min |
| Frage mit Quellen | ~3,5 min |
| Agent-Auftrag mit Vorschlag | ~8 min |
| Embedding (`bge-m3`) | ~10 s |

Bekannte Grenzen von `qwen3:8b` im Rundgang: Den Arztbrief stufte es als „Sonstiges“ ein (Docling liefert die Tabelle als Fließtext), und auf die Frage kam keine Antwort mit gültigen Quellenangaben. Die App zeigt dann „keine belegte Antwort“ statt einer unbelegten.

`qwen3:8b` schreibt dort etwa 1,3 Tokens/s. Deshalb wartet der lokale Modus länger als der öffentliche (`OLLAMA_TIMEOUT_SECONDS`, `PIPELINE_STEP_SECONDS`, `AGENT_MAX_SECONDS`, `API_WAIT_SECONDS`, siehe [Konfiguration](docs/specs/konfiguration.md)). Der Agent bekommt sein Token lokal selbst signiert, weil Keycloak beim Token Exchange kein `act` ausstellt ([ADR 0012](docs/architecture/adr/0012-agent-token.md)).

## Dokumentation

- Architektur: [`docs/architecture/architecture.md`](docs/architecture/architecture.md)
- Feature-Specs: [`docs/specs/`](docs/specs/)
- Bedrohungsmodell: [`docs/security/threat-model.md`](docs/security/threat-model.md)
- Projektbeschreibung: [`docs/projektbeschreibung.md`](docs/projektbeschreibung.md) – Text ändern, dann `make project-description` (kopiert ihn in die App); Bilder neu mit `make screens`
