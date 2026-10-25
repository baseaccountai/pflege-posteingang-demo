# Pflege-Posteingang Demo – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Öffentlich erreichbare, mobil nutzbare Bewerbungs-Demo „Pflege-Posteingang“, die sichere KI für Pflegedokumente zeigt (OIDC, RLS, RAG, Agenten-Autorisierung, Pseudonymisierung, Prompt-Injection-Schutz) und komplett lokal betreibbar ist.

**Architecture:** Monorepo mit Next.js-Web-App als Backend-for-Frontend (OIDC-Login serverseitig, Tokens nie im Browser) und FastAPI-Backend als Sicherheitsschicht vor Mistral/Ollama und Supabase (Postgres, pgvector, Storage, RLS). Anbieter (OCR, LLM, Embeddings, IdP) sind per Konfiguration austauschbar.

**Tech Stack:** Next.js (App Router), TypeScript, Tailwind, shadcn/ui, PWA (Serwist), Vitest, Playwright · Python ≥ 3.12, FastAPI, uv, pytest · Supabase · Zitadel (öffentlich) / Keycloak (lokal) · Mistral (OCR, Small, Ministral, embed) / Docling + Ollama (lokal) · Docker Compose · GitHub Actions · Vercel + Koyeb (Frankfurt).

**Spec:** `docs/superpowers/specs/2026-10-23-pflege-posteingang-demo-design.md` — immer mitlesen.

## Global Constraints

- **Frist:** Stufe 1 online bis **02.11.2026**; bewerbungsfertig bis **10.11.2026**; Bewerbungsfrist 11.11.2026.
- **Nur Musterdaten**: erfundene Personen; gelbes Banner „MUSTERDATEN · keine echten Personen“ auf jedem Bildschirm; Wasserzeichen „MUSTER“ auf Musterdokumenten.
- **Upload-Hinweis** wörtlich: „Bitte keine echten Personendaten hochladen.“
- **Footer** wörtlich: „Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt“. Keine Logos der Hochschule.
- **Sprache:** Oberfläche und Doku Deutsch; Code, Bezeichner, Commits Englisch.
- **Spec-Regel:** Kein Feature-Code ohne vom Bewerber freigegebene Spec (`docs/specs/Fxx-<name>/{requirements,design,tasks}.md`, Kiro-Stil, Akzeptanzkriterien in EARS-Form).
- **TDD:** erst Test, dann Code; jedes Akzeptanzkriterium hat ≥ 1 Test; `tasks.md` verweist auf Kriterium-IDs.
- **Tokens nie im Browser** (HttpOnly-Session-Cookie im BFF).
- **Backend greift im Namen des Nutzers/Agenten auf Supabase zu**, nie mit Service-Key für Nutzerdaten (Service-Key nur für Seed/Reset).
- **Anbieterwechsel nur per Konfiguration** (Env-Variablen), nie per Codeänderung.
- **Budget** ca. 10–15 € bis zur Bewerbung; Tagesobergrenze für Mistral-Kosten im Backend.
- **Bei Zeitnot** wird zuerst der vollständige lokale Betrieb (Ollama/Docling/Keycloak/Supabase self-hosted) reduziert, nie die Sicherheitsfeatures.
- **Halte-Punkt nach jeder Phase:** Tests grün (Ausgabe zeigen) → Codex-Review → Zusammenfassung → **Stopp, Bewerber entscheidet**.

## Review Focus

- **Rollenwechsel mitten in einer Sitzung** (WB1 → WB2): danach darf keine zwischengespeicherte Seite, Antwort oder Vektor-Suche noch WB1-Daten zeigen → Test in F01/F08 (Playwright: Rolle wechseln, Bewohnerliste + Chat-Verlauf prüfen).
- **Schlechte Scans** (schief, unscharf, leere Seite, Nicht-Pflegedokument): Erwartung freundliche Meldung statt leerer/halluzinierter Felder → Test in F02/F03 mit Musterbildern `samples/bad/`.
- **Supabase/Koyeb aus dem Schlaf oder Mistral-Limit erreicht**: Erwartung sichtbarer Hinweis „Demo startet / Tageskontingent erreicht“, Musterdaten weiter ansehbar → Test in F10 (API-Attrappe liefert 503/429).
- **Frage zu einem Bewohner, den es nicht gibt oder der im fremden Wohnbereich liegt**: Antwort darf nicht verraten, ob er existiert („Keine Treffer in deinem Wohnbereich“) → Test in F05/F08.
- **Dokument wird einem falschen Bewohner zugeordnet**: Freigabe-Schritt muss den Bewohner explizit bestätigen lassen und änderbar machen → Test in F03.

---

## Phasenübersicht

| Phase | Inhalt | Detailplan | Abnahme (Halte-Punkt) |
|---|---|---|---|
| 0 | Gerüst, Skills, CLAUDE.md, arc42 + ADRs, CI, Konten | **unten, Tasks 0.1–0.7** | `make test` grün lokal + in CI; Codex-Review |
| 1 | Specs Stufe 1: F01–F05, F09–F11 | Task 1.1 | Bewerber gibt alle Stufe-1-Specs frei |
| 2 | F01 Login & Rollen, DB-Schema, RLS; Spike Token Exchange | `docs/specs/F01-*/tasks.md` | RLS-Tests grün; Login öffentlich + lokal |
| 3 | F02, F03, F04, F10 (Musterdaten, Reset, Hinweise) | jeweilige `tasks.md` | Papier → Akte durchgängig (E2E) |
| 4 | F05 RAG, F09 Landkarte, F11 Deployment | jeweilige `tasks.md` | **Stufe 1 öffentlich erreichbar** |
| 5 | Specs Stufe 2: F06–F08, F12, F13 | Task 5.1 | Freigabe durch Bewerber |
| 6 | F06 Pseudonymisierung, F07 Injection-Schutz | jeweilige `tasks.md` | Erkennungsrate auf Testkorpus im Bericht |
| 7 | F08 Agent + Token Exchange, F12 Protokoll, F13 Sicherheitstests | jeweilige `tasks.md` | WB2 sieht nichts aus WB1 – auch als Agent (E2E) |
| 8 | Lokaler Betrieb komplett (Ollama, Docling, Keycloak), Feinschliff | eigene `tasks.md` in `docs/specs/F11-*` | `docker compose … up` startet alles, Smoke-Test grün |
| 9 | Projektbeschreibung + Seite „Über das Projekt“ | Task 9.1 | Bewerber nimmt Text ab |

---

## Phase 0 – Gerüst (Detail)

### Datei-Struktur nach Phase 0

```
README.md  CLAUDE.md  Makefile  .gitignore  .env.example
docs/architecture/architecture.md
docs/architecture/adr/0001-python-fastapi-backend.md … 0006-kiro-spec-format.md
docs/architecture/diagrams/context.md
docs/specs/README.md  docs/specs/_template/{requirements,design,tasks}.md
docs/security/threat-model.md   (Gerüst)
apps/web/   (Next.js + Tailwind + shadcn/ui + Vitest + Playwright)
apps/api/   (FastAPI + uv + pytest)
supabase/   (supabase init)
infra/docker-compose.yml
.github/workflows/ci.yml
```

### Task 0.1: Repository, Skills, Arbeitsregeln

**Files:**
- Create: `.gitignore` (enthält `.superpowers/`, `.env`, `node_modules/`, `.venv/`, `__pycache__/`, `.next/`)
- Create: `CLAUDE.md`, `README.md` (Kurzfassung + „in Arbeit“), `.env.example`
- Move: vorhandene Dateien bleiben; `Job-Wissenschaft-HS-Anhalt.pdf` und `brainstorming_prompt.md` → `docs/background/`

**Interfaces:**
- Produces: Git-Repo auf Branch `main`; `CLAUDE.md` mit den Global Constraints dieses Plans (verdichtet) + Halte-Punkt-Regel + Verweis auf Design und Plan.

- [ ] **Step 1:** `git init -b main`, Dateien anlegen/verschieben wie oben.
- [ ] **Step 2:** Skills installieren: `npx skills add shadcn/ui` und `npx skills add supabase/agent-skills` (im Projektordner). Expected: Skills unter `.claude/skills/` vorhanden.
- [ ] **Step 3:** Verifizieren: `git status` zeigt keine Dateien aus `.superpowers/`.
- [ ] **Step 4: Commit** — `git add -A && git commit -m "chore: initialize repository, project rules and skills"`

### Task 0.2: FastAPI-Grundgerüst mit Health-Endpoint

**Files:**
- Create: `apps/api/pyproject.toml` (uv; Python ≥ 3.12; deps: fastapi, uvicorn, pydantic-settings; dev: pytest, httpx, ruff)
- Create: `apps/api/app/main.py`, `apps/api/app/config.py`
- Test: `apps/api/tests/test_health.py`

**Interfaces:**
- Produces: `app.main:app` (FastAPI); `GET /health` → `200 {"status": "ok", "llm_provider": <str>, "ocr_provider": <str>}`; `app.config.Settings` mit Feldern `llm_provider: Literal["mistral","ollama"] = "mistral"`, `ocr_provider: Literal["mistral","docling"] = "mistral"` aus Env `LLM_PROVIDER`, `OCR_PROVIDER`.

- [ ] **Step 1: Failing test**

```python
def test_health_reports_providers(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "llm_provider": "mistral", "ocr_provider": "mistral"}

def test_health_reflects_env(monkeypatch, make_client):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OCR_PROVIDER", "docling")
    assert make_client().get("/health").json()["llm_provider"] == "ollama"
```

(`client`/`make_client` als Fixtures in `tests/conftest.py`, App per Factory `create_app()` erzeugen.)

- [ ] **Step 2:** `cd apps/api && uv run pytest -v` → FAIL (Modul fehlt).
- [ ] **Step 3:** `create_app() -> FastAPI` in `app/main.py`, `Settings` in `app/config.py` implementieren.
- [ ] **Step 4:** `uv run pytest -v` → PASS; `uv run ruff check .` → keine Fehler.
- [ ] **Step 5: Commit** — `feat(api): add FastAPI skeleton with configurable providers`

### Task 0.3: Next.js-Grundgerüst mit Muster-Banner und Footer

**Files:**
- Create: `apps/web/` via `create-next-app` (TypeScript, App Router, Tailwind, ESLint, pnpm), `shadcn init`
- Create: `apps/web/src/components/demo-banner.tsx`, `apps/web/src/components/site-footer.tsx`, `apps/web/src/app/layout.tsx` (bindet beide ein, `lang="de"`)
- Test: `apps/web/src/components/__tests__/demo-banner.test.tsx`, `apps/web/e2e/smoke.spec.ts`

**Interfaces:**
- Produces: `<DemoBanner />` (Text exakt „MUSTERDATEN · keine echten Personen“), `<SiteFooter />` (Text exakt aus Global Constraints); Playwright-Projekte `desktop` und `mobile` (Pixel 7).

- [ ] **Step 1: Failing tests** — Vitest: Banner rendert den exakten Text. Playwright `smoke.spec.ts`: Startseite zeigt Banner und Footer-Text in beiden Projekten.
- [ ] **Step 2:** `pnpm test` und `pnpm exec playwright test` → FAIL.
- [ ] **Step 3:** Komponenten implementieren, im Layout einbinden.
- [ ] **Step 4:** Beide Testläufe → PASS; `pnpm lint` sauber.
- [ ] **Step 5: Commit** — `feat(web): add Next.js skeleton with demo banner and disclaimer footer`

### Task 0.4: Docker Compose und Makefile

**Files:**
- Create: `apps/api/Dockerfile`, `apps/web/Dockerfile`, `infra/docker-compose.yml` (Dienste `web`:3000, `api`:8000), `Makefile`

**Interfaces:**
- Produces: `make test` (api pytest + web vitest), `make e2e`, `make up` (= `docker compose -f infra/docker-compose.yml up --build`).

- [ ] **Step 1:** Dateien anlegen; `web` erreicht `api` über `API_BASE_URL=http://api:8000`.
- [ ] **Step 2:** `make up`, dann `curl -s localhost:8000/health` → `{"status":"ok",…}`; `curl -s localhost:3000` enthält „MUSTERDATEN“.
- [ ] **Step 3:** `make test` → alle grün.
- [ ] **Step 4: Commit** — `build: add Docker Compose setup and Makefile`

### Task 0.5: CI-Pipeline

**Files:**
- Create: `.github/workflows/ci.yml` (Jobs: `api` – uv, ruff, pytest; `web` – pnpm, lint, vitest, playwright mit beiden Projekten)

- [ ] **Step 1:** Workflow schreiben; lokal mit `act` optional prüfen.
- [ ] **Step 2:** Nach Push auf GitHub (öffentliches Repo, vom Bewerber angelegt): beide Jobs grün.
- [ ] **Step 3: Commit** — `ci: add test pipeline for api and web`

### Task 0.6: Architektur- und Spec-Gerüst

**Files:**
- Create: `docs/architecture/architecture.md` (arc42-Kapitel: 1 Ziele, 3 Kontext, 5 Bausteine, 6 Laufzeit, 7 Verteilung, 8 Querschnitt/Sicherheit, 9 Entscheidungen → ADR-Liste, 11 Risiken — befüllt aus Design-Abschnitten 5 und 10)
- Create: ADRs 0001 Python/FastAPI, 0002 Supabase, 0003 Mistral Cloud / Ollama lokal, 0004 Next.js als BFF, 0005 Zitadel öffentlich / Keycloak lokal, 0006 Kiro-Spec-Format (je: Kontext, Entscheidung, Alternativen, Konsequenzen)
- Create: `docs/architecture/diagrams/context.md` (C4-Kontext + Container als Mermaid)
- Create: `docs/specs/README.md` (Ablauf, Status-Tabelle F01–F14), `docs/specs/_template/{requirements,design,tasks}.md` (EARS-Beispiel: „WENN eine Pflegekraft aus WB2 die Akte eines Bewohners aus WB1 aufruft, DANN soll das System ‚Kein Zugriff' anzeigen und keine Daten ausliefern.“; Kriterium-IDs `Fxx-ACn`)
- Create: `docs/security/threat-model.md` (Gerüst nach OWASP Top 10 für LLM-Anwendungen)

- [ ] **Step 1:** Dateien schreiben; jede Aussage muss aus dem Design-Dokument belegbar sein.
- [ ] **Step 2:** Mermaid-Diagramme rendern prüfen (GitHub-Vorschau oder `npx @mermaid-js/mermaid-cli`).
- [ ] **Step 3: Commit** — `docs: add arc42 architecture, ADRs, spec template and threat model skeleton`

### Task 0.7: Konten und Geheimnisse (mit dem Bewerber)

Der Bewerber legt die Konten an; Claude führt Schritt für Schritt durch und prüft danach.

- [ ] Supabase-Projekt (Region Frankfurt) · Zitadel-Cloud-Instanz · Mistral-Konto mit Bezahlplan nach Verbrauch (**prüfen und in ADR 0003 festhalten: keine Trainingsnutzung der Eingaben**; aktuelle Modellversionen von Mistral Small, Ministral, mistral-embed, Mistral OCR notieren) · Koyeb (Frankfurt, Instanz ≥ 2 GB RAM, Preis notieren) · Vercel · GitHub-Repo öffentlich.
- [ ] Alle Schlüssel nur in `.env` (lokal) bzw. in den Secret-Stores von GitHub/Vercel/Koyeb; `.env.example` listet alle Variablennamen ohne Werte.
- [ ] Verifizieren: `git grep -i -E "sk-|api_key=|secret="` findet nichts außer `.env.example`-Platzhaltern.
- [ ] **Commit** — `docs: record provider versions and account setup`

### Halte-Punkt Phase 0
- [ ] `make test` lokal grün (Ausgabe zeigen), CI grün.
- [ ] Codex-Review des gesamten Stands; Befunde bewerten (superpowers:receiving-code-review), berechtigte umsetzen.
- [ ] Zusammenfassung an Bewerber; **Stopp bis Freigabe**.

---

## Phase 1 / 5 – Specs schreiben

### Task 1.1 (Stufe 1) und Task 5.1 (Stufe 2): Feature-Specs

Für jedes Feature der Stufe (Stufe 1: F01, F02, F03, F04, F05, F09, F10, F11; Stufe 2: F06, F07, F08, F12, F13) einen Ordner `docs/specs/Fxx-<name>/` aus dem Template:

- [ ] `requirements.md`: User Stories + EARS-Akzeptanzkriterien `Fxx-ACn`; Inhalte aus Design-Abschnitten 5–7; Review-Focus-Punkte dieses Plans als Kriterien aufnehmen.
- [ ] `design.md`: Komponenten, Datenmodell (Tabellen/Spalten, RLS-Policies), API-Endpunkte mit Request/Response, Sicherheitsaspekte, Tests je Ebene (Design 8.1).
- [ ] `tasks.md`: TDD-Schritte im Format dieses Plans (Test → Fail → Code → Pass → Commit), jede Aufgabe mit `Fxx-ACn`-Verweis.
- [ ] Status-Tabelle in `docs/specs/README.md` aktualisieren.
- [ ] **Halte-Punkt:** Bewerber liest und gibt frei (gebündelt pro Stufe). Codex-Review der Specs auf Widersprüche und Lücken.

Pflichtinhalte, die in den Specs nicht fehlen dürfen:
- **F01:** Authorization Code + PKCE; Rollenwechsel per Logout + Login mit Zugangsdaten zum Kopieren; Spike „Zitadel/Keycloak-Token → Supabase-RLS-Claims (Rolle, Wohnbereich)“ als erste Aufgabe; Rollen WB1, WB2, PDL. **Demo-Nutzer als Code:** Zitadel per Setup-Skript über die Management-API (oder Terraform-Provider) in `infra/zitadel/`, Keycloak per Realm-Import in `infra/keycloak/` – gleiche Nutzer, Rollen und Claims; Demo-Konten ohne Admin-Rechte im IdP, Passwortänderung gesperrt. **Token-Prüfung im Backend:** Signatur über JWKS, `iss`, `aud`, `exp`, erlaubte Algorithmen fest; Vertrauensgrenze im Bedrohungsmodell dokumentieren.
- **F02/F03:** Kamera/Upload; Upload-Hinweis; Upload-Limit pro Sitzung; Bewohner-Zuordnung explizit bestätigen; neu/abgesetzt/unverändert bei Medikation.
- **F04:** Herkunft je Eintrag; Kennzeichnung „vom Agenten angelegt · bestätigt von …“.
- **F05:** Chunking strukturbasiert + Recursive Splitting als Rückfall, Tabellen ganz, Metadaten (Bewohner, Wohnbereich, Dokumenttyp, Datum, Seite, Dokument-ID); Quellen in jeder Antwort; Suche pro Bewohner.
- **F06:** Pseudonymisierung nach OCR und vor Feldextraktion, Embeddings und Chat; Bewohnerbezug über ID-Metadaten; Hinweis in der App, dass Cloud-OCR Rohdaten sieht.
- **F07:** fünf Schichten (Design 5.5a); getrennte Ordner `apps/api/security/patterns/` und `tests/security/corpus/`; zwei präparierte Dokumente.
- **F08:** Werkzeuge und Verbotsliste (Design 5.5); Token Exchange RFC 8693 mit `act`-Claim, Gültigkeit wenige Minuten, Rückfall per selbst signiertem Agenten-JWT.
- **F09:** Karte „Über das Projekt“ ganz oben, Anforderungs-Landkarte darunter.
- **F10:** nächtlicher Reset, Keep-alive, Tageskostenobergrenze, Hinweise bei Schlaf/Limit.
- **F11:** Deployment Vercel + Koyeb (Frankfurt) per GitHub Actions; **PWA** (Manifest, Service Worker via Serwist, installierbar, untere Navigation Start · Posteingang · Bewohner · Fragen); Compose-Profil `local-llm` (Ollama, Docling) für Phase 8.
- **F12:** Protokoll (wer, wann, Mensch oder Agent, welches Modell, was blockiert), nur PDL.
- **F13:** Sicherheitstests (Testkorpus + garak/promptfoo) in CI, Bericht nach `docs/security/reports/`.
- **F14 (Kann, nur bei Zeit):** Vergleich Cloud vs. lokal und strukturbasiertes vs. reines Recursive Chunking.

---

## Phase 9 – Projektbeschreibung

### Task 9.1: Projektbeschreibung und „Über das Projekt“

**Files:**
- Create: `docs/projektbeschreibung.md` (Abschnitte laut Design 8.3, aus dem **tatsächlichen** Stand; Screenshots per Playwright nach `docs/assets/screens/`)
- Create: `apps/web/src/app/projekt/page.tsx` (rendert die Markdown-Datei)
- Modify: Startseite (Karte ganz oben), Kopfzeile (dauerhafter Eintrag „Über das Projekt“), `README.md` (Kurzfassung + Link)
- Test: `apps/web/e2e/projekt.spec.ts`

- [ ] **Step 1: Failing test** — Playwright (desktop + mobile): Kopfzeile enthält Link „Über das Projekt“ auf jeder Hauptseite; Startseite zeigt die Karte oberhalb der Anforderungs-Landkarte; `/projekt` zeigt Überschrift „Was die Anwendung macht“.
- [ ] **Step 2:** Test → FAIL.
- [ ] **Step 3:** Text schreiben (gemessene Werte aus `docs/security/reports/` übernehmen, keine Planwerte), Seite und Links umsetzen.
- [ ] **Step 4:** Test → PASS.
- [ ] **Step 5: Commit** — `docs: add project description and in-app about page`
- [ ] **Halte-Punkt:** Bewerber nimmt den Text ab.
