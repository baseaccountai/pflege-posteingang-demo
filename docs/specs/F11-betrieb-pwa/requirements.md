# F11 – Docker Compose lokal, CI/CD, Deployment, PWA: Anforderungen

Status: freigegeben 25.10.2026, geändert 27.10.2026 (API-Hosting Vercel statt Koyeb) · Stufe: 1 (Keycloak, Ollama, Docling: Phase 8, AC13–AC21 freigegeben 01.11.2026) · Bildschirme: alle

## Einführung

Die Demo läuft öffentlich (Vercel für Web und API + Supabase + Zitadel) und lokal per Docker Compose; Tests und Deployment laufen über **einen** GitHub-Actions-Ablauf, der nur geprüfte Commits veröffentlicht. Auf dem Handy ist sie als PWA installierbar. Grundlage: Design 3, 4, 5.1, 6 (untere Navigation), 9.

> **Änderung 27.10.2026 – warum die API auf Vercel statt auf Koyeb läuft** (Entscheidung des Bewerbers, Details [ADR 0011](../../architecture/adr/0011-api-on-vercel.md)):
> Mistral AI hat Koyeb im Februar 2026 übernommen. Neue Konten erhalten seitdem keinen Starter-Tarif mehr, sondern starten im Pro-Tarif für 29 $/Monat zuzüglich Rechenzeit. Damit allein wäre das Budget (10–15 € bis zur Bewerbung, davon ein Teil für Mistral) überschritten. Vercel betreibt FastAPI im Hobby-Tarif kostenlos (2 GB RAM, 300 s je Anfrage, Region `fra1`) und ist für das Web ohnehin im Einsatz. Folgen: Ausrollen ohne Container-Image; LLM Guard läuft öffentlich nicht (500-MB-Grenze, Prüfung per Mistral-Modell); ob Hintergrundarbeit nach dem 202 zu Ende läuft, klärt Spike S5 (sonst F02 Aufgabe 10). Rückfallebene: Hetzner-VPS.

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
| F11-AC5 | `make up` soll lokales Supabase (CLI) sowie Web und API (Docker; *28.10.2026, Entscheidung Bewerber: ohne Compose-Plugin, per `docker run` in `infra/local-stack.sh`*) starten; `make up-test` zusätzlich den Test-OIDC-Server. Keycloak und das Profil `local-llm` (Ollama, Docling) folgen in Phase 8. |
| F11-AC6 | Die CI soll bei jedem Push und Pull Request ausführen: ruff, pytest (Unit), Datenbank- und Integrationstests gegen lokales Supabase, ESLint, Vitest, Playwright (desktop + mobile) gegen Test-OIDC-Server, Secret-Scan (gitleaks). |
| F11-AC7 | WENN die CI für einen Commit auf `main` vollständig grün ist, DANN soll ein Deploy-Workflow für **genau diesen Commit** nacheinander die Migrationen auf Supabase anwenden, die API auf Vercel (eigenes Projekt, Produktion, Region `fra1`) und das Web auf Vercel (Produktion, Region `fra1`) ausrollen; Deploy-Läufe laufen nie parallel. |
| F11-AC8 | FALLS ein Schritt des Deploy-Workflows fehlschlägt, DANN soll kein späterer Schritt starten. |
| F11-AC9 | Vercel soll Produktions-Deployments von Web **und API** nur über den Deploy-Workflow erhalten; automatische Git-Deployments sind für `main` abgeschaltet, Vorschau-Deployments für andere Branches bleiben. |
| F11-AC10 | Alle Geheimnisse sollen nur in den Secret-Stores von GitHub und Vercel bzw. lokal in `.env` liegen; `.env.example` listet alle Variablennamen ohne Werte (Übersicht: [konfiguration.md](../konfiguration.md)). |
| F11-AC11 | Das System soll auf allen Seiten HTTP-Sicherheitsheader setzen: `Content-Security-Policy` mit Nonce pro Anfrage (ohne `unsafe-eval`, ohne `unsafe-inline` für Skripte), `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (Kamera nur `self`); der Produktionsbuild erzeugt dabei keine CSP-Verletzungen. |
| F11-AC12 | Die API soll keine Browser-Origins erlauben (CORS gesperrt) und jede Fach-Route nur mit gültigem Token und BFF-Nachweis beantworten (F01-AC6, F01-AC8). |

## Phase 8 – Lokaler Betrieb komplett

Status: **freigegeben 01.11.2026** · Grundlage: Design 3 („komplett lokal betreibbar“), 5.1 (Tabelle öffentlich/lokal), 10 (Docling braucht RAM) · Ergänzt F11-AC5.

- **US-4:** Als Professor möchte ich sehen, dass dieselbe Anwendung ohne jeden Cloud-Dienst läuft – Login, OCR, Modelle und Datenbank auf einem Rechner –, damit „im lokalen Modus sieht kein fremdes Modell die Daten“ belegt ist.

| ID | Kriterium |
|---|---|
| F11-AC13 | `make up-local` soll ohne Cloud-Konto und ohne `.env` starten: lokales Supabase (CLI, Seed), Keycloak mit vorkonfiguriertem Realm, Docling, API und Web (Docker, Host-Netzwerk wie AC5) mit `LLM_PROVIDER=ollama`, `OCR_PROVIDER=docling` und festen lokalen Geheimnissen. Ollama läuft auf dem Rechner selbst (nicht im Container). `make down` beendet alles außer Ollama. |
| F11-AC14 | WENN Ollama nicht erreichbar ist oder das Chat- bzw. Embedding-Modell fehlt, DANN soll `make up-local` vor dem Start der Container abbrechen und den nötigen Befehl nennen (`ollama pull <modell>`). |
| F11-AC15 | Der Keycloak-Realm soll die Rollen `nurse_wb1`, `nurse_wb2`, `pdl` und die drei Demo-Nutzer aus `infra/demo-users.json` enthalten (dieselben absichtlich öffentlichen Demo-Passwörter wie bei Zitadel, F01-AC2) und die Rollen als Liste im Claim `roles` ausgeben; Login per Code-Flow mit PKCE ohne Codeänderung (F01-AC19, nur Konfiguration). Direktes Passwort-Login (Direct Access Grant) bleibt aus. |
| F11-AC16 | Der Agent soll lokal ein Agenten-Token erhalten: per Token Exchange in Keycloak (RFC 8693), FALLS Keycloak ein Token mit `act`-Claim ausstellt, sonst über den Rückfall `self_signed` (ADR 0012); der gewählte Weg wird im ADR ergänzt und auf `/projekt` angezeigt (F08-AC2). |
| F11-AC17 | WO `OCR_PROVIDER=docling` gesetzt ist, soll die API PDF und Foto an den lokalen Docling-Dienst geben und Markdown je Seite erhalten – im selben Format wie bei Mistral OCR (F02); ist Docling nicht erreichbar oder antwortet mit Fehler oder nach dem Zeitlimit, DANN gilt das Dokument als „OCR nicht verfügbar“ (F02-Fehlerweg, erneut versuchbar). |
| F11-AC18 | WO `LLM_PROVIDER=ollama` gesetzt ist, sollen Feldvorschlag, Antworten, Agent (Function Calling), Injection-Prüfmodell und Embeddings (1024 Dimensionen) über Ollama laufen, und die API soll keinen Mistral-Client erzeugen – auch nicht, wenn ein `MISTRAL_API_KEY` gesetzt ist. |
| F11-AC19 | `make reindex` soll alle freigegebenen Dokumente mit dem konfigurierten Embedding-Modell neu indizieren (erfüllt F05-AC13); `make up-local` ruft es nach dem Seed auf, weil die Seed-Chunks mit `mistral-embed` berechnet sind. Es läuft nur gegen die lokale Datenbank. |
| F11-AC20 | `make smoke-local` soll prüfen: Startseite, `/health` meldet `ollama`/`docling`, OIDC-Discovery von Keycloak, und eine Probe gegen die echten lokalen Dienste – Docling liest den Musterbrief `arztbrief_muster-bauer.pdf` (enthält „Ramipril“), Ollama liefert einen gültigen Feldvorschlag, einen Werkzeugaufruf und einen 1024er-Vektor. |
| F11-AC21 | README und Projektbeschreibung (Abschnitt Betrieb) sollen den lokalen Start in wenigen Befehlen nennen, mit Speicherbedarf und Modellen. |
| F11-AC22 | Das System soll Suchmaschinen die Aufnahme untersagen: Die Web-App soll auf allen Pfaden den Header `X-Robots-Tag: noindex, nofollow` senden und jede Seite `<meta name="robots" content="noindex, nofollow">` tragen; die API soll auf jeder Antwort `X-Robots-Tag: noindex, nofollow` senden. Eine `robots.txt`-Sperre gibt es bewusst nicht, weil ein Crawler das `noindex` sonst nie liest. (Bewerber-Entscheidung 03.11.2026) |

## Nicht im Umfang

Monitoring; Supabase self-hosted ohne CLI (die CLI startet Supabase bereits als lokale Container); Ollama im Container (läuft nativ, schneller und ohne doppelten Modell-Download); Playwright-Lauf gegen echte lokale Modelle in der CI (zu langsam für CI-Rechner, die Probe in AC20 deckt es lokal ab); Modellvergleich Cloud gegen lokal (F14, „Kann“ – optional als Aufgabe 15).
