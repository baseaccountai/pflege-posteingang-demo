# Design: Bewerbungs-Demo „Pflege-Posteingang“ (sichere KI für Pflegedokumente)

Stand: 23.10.2026 · Status: Entwurf zur Freigabe

Legende: **[Entscheidung]** = vom Bewerber festgelegt · **[Annahme Claude]** = von Claude gesetzt, prüfbar/änderbar

---

## 1. Zweck und Warum

Der Bewerber bewirbt sich auf die Stelle **Nr. 479, Wissenschaftlicher Mitarbeiter Web Engineering, Hochschule Anhalt (Köthen)**. Die Stelle ist Teil des Verbundprojekts **KLARA – KI-Labor für verantwortungsvolle Anwendung, Reflexion und Akzeptanz in der Pflege**. Die Professur Web Engineering verantwortet darin die **Sicherheitsarchitektur für die datenschutzkonforme Integration generativer KI**: Autorisierung von KI-Agenten, Absicherung von RAG gegen Prompt-Injection, Vergleich von Cloud- und lokalen Sprachmodellen.

Die Demo ist ein **Arbeitsnachweis**. Sie wird als öffentlicher Link im Anschreiben genannt.

**Erfolg [Entscheidung]:** Wer den Link öffnet (primär die Professur Web Engineering), erkennt **innerhalb von zwei Minuten**, dass die Punkte aus „Sie verfügen über …“ in einer laufenden Anwendung umgesetzt sind:

| „Sie verfügen über …“ | Sichtbar in der Demo durch |
|---|---|
| Softwarearchitektur, Web-Backend (Python/TypeScript) | arc42-Architektur, ADRs, Next.js + FastAPI im öffentlichen Repo |
| Anbindung von LLMs über APIs | Mistral OCR + Mistral LLM/Embeddings |
| RAG, agentenbasierte KI | Fragen an Dokumente mit Quellen; Agent legt Wiedervorlagen an |
| IT-/API-Sicherheit, OAuth 2.0/OIDC | OIDC-Login, Rollen, Datenbankrechte (RLS), Rechte des Agenten |
| *wünschenswert:* lokale Modelle | Umschaltbar auf Ollama + Docling per Konfiguration |
| *wünschenswert:* Docker, CI/CD | Docker Compose für lokalen Betrieb, GitHub Actions |
| *wünschenswert:* Sicherheitsrisiken von LLM-Anwendungen | Prompt-Injection-Erkennung mit präpariertem Testdokument, Bedrohungsmodell |

**Bewerber-Profil (bestimmt Schwerpunkte):** stark in lokalen Modellen; etwas Erfahrung mit RAG und OAuth2; JavaScript-Praxis (u. a. ExtJS); Docker-Grundlagen; CI/CD mit Bamboo. **Kein Python genannt.** Die Demo soll gezielt die Lücken (Python-Backend, LLM-Sicherheit, Agenten-Autorisierung, DSGVO/AI Act) belegen.

## 2. Szenario (Pflegekontext)

**[Entscheidung]** Papierdokumente sind ein großer Bürokratietreiber in der Pflege (laut Allensbach-Studie für die Landespflegekammer dokumentieren 45 % der Pflegekräfte 2,5–5 h täglich; Medikationspläne und Überleitungsbögen kommen weiterhin auf Papier).

Die Demo ist der **digitale Posteingang einer Pflegeeinrichtung**:

1. Pflegekraft fotografiert/lädt ein Papierdokument hoch (Arztbrief, Medikationsplan, Überleitungsbogen).
2. OCR + KI schlagen strukturierte Felder vor (Diagnosen, Medikamente neu/abgesetzt, Wiedervorlagen); **ein Mensch prüft und gibt frei**.
3. Freigegebene Daten landen in der **Bewohnerakte**, jeder Eintrag mit Herkunftsdokument.
4. Pflegekräfte stellen **Fragen an die Dokumente (RAG)** und erhalten Antworten mit Quellen.
5. Sicherheit wird sichtbar: Pseudonymisierung vor dem LLM, erkannte Prompt-Injection, Agent sieht nie mehr als sein Nutzer.

## 3. Ziele, Nicht-Ziele, Anti-Ziele

**Ziele**
- Öffentlich erreichbare, mobil gut nutzbare Web-App (PWA) bis spätestens **10.11.2026** (Frist Bewerbung: 11.11.2026).
- Zeigt die Anforderungen aus Abschnitt 1 erkennbar und ausprobierbar.
- Komplett lokal betreibbar inkl. lokalem LLM (Ollama) und lokaler OCR (Docling) — **[Entscheidung]** öffentlich läuft kein lokales Modell.
- Spec-getriebene Entwicklung, im Repo nachvollziehbar.

**Nicht-Ziele**
- Keine echte Pflegedokumentation, keine Anbindung an Telematikinfrastruktur/ePA, keine FHIR-Schnittstellen.
- Keine Benutzerverwaltung über feste Demo-Konten hinaus, keine Registrierung.
- Keine Mehrsprachigkeit.
- Kein lokales Modell im öffentlichen Betrieb.

**Anti-Ziele (wäre ein Fehlschlag, selbst wenn es technisch läuft)**
- Der Professor findet in zwei Minuten nicht, wo die Anforderungen umgesetzt sind.
- Ein „weiterer Chatbot“ ohne sichtbare Sicherheitsarchitektur.
- Echte oder echt wirkende Personendaten; Besucher-Uploads, die dauerhaft gespeichert bleiben.
- Die Demo wirkt wie ein offizielles Produkt der Hochschule Anhalt oder des KLARA-Verbunds.
- Link ist am Tag des Lesens nicht erreichbar oder lädt minutenlang ohne Hinweis.

## 4. Rahmenbedingungen

| Thema | Vorgabe |
|---|---|
| Zeit | 24.10.–11.11.2026, ca. **4 h/Tag**, ≈ 68 h Projektzeit **[Annahme Claude: „4 Stunden“ = pro Tag]** |
| Kosten | **Budget ca. 10–15 € bis zur Bewerbung [Entscheidung]**: Mistral nach Verbrauch (kein Training auf Eingaben — beim Anlegen prüfen), Backend-Server mit genug RAM für Presidio + LLM Guard (*27.10.2026: Vercel Hobby, 0 €, ADR 0011; Koyeb ohne günstigen Tarif; Rückfall Hetzner*). Tagesobergrenze für Mistral-Kosten im Backend. |
| Streichreihenfolge bei Zeitnot | **Sicherheitsfunktionen haben Vorrang [Entscheidung]**: zuerst wird der vollständige lokale Betrieb (Ollama, Docling, Keycloak, Supabase self-hosted) reduziert; Web + API per Docker laufen immer. |
| Herkunft der Tools | europäisch bevorzugt; US-Anbieter mit EU-Rechenzentrum akzeptiert **[Entscheidung]** |
| Daten | **ausschließlich erfundene, sichtbar markierte Musterdaten [Entscheidung]** |
| Geräte | Handy, Tablet, Desktop; installierbar als PWA; Kamera für Scans |
| Sprache | Oberfläche und Doku Deutsch, Code und Commits Englisch **[Entscheidung]** |
| Repo | ein öffentliches GitHub-Monorepo **[Entscheidung]** |

## 5. Technische Festlegungen

### 5.1 Stack [Entscheidung]

| Rolle | Öffentlich | Lokal |
|---|---|---|
| Web-App | **Next.js** (App Router) + **Tailwind** + **shadcn/ui**, PWA, auf **Vercel** | Docker |
| Backend | **Python / FastAPI** auf **Vercel** (eigenes Projekt, `fra1`) — *geändert 27.10.2026, vorher Koyeb; Begründung: [ADR 0011](../../architecture/adr/0011-api-on-vercel.md)* | Docker (lokal) |
| Daten, Vektoren, Dateien, Rechte | **Supabase** (Region Frankfurt): Postgres, pgvector, Storage, Row Level Security | Supabase self-hosted (Docker) |
| Login (OIDC) | **Zitadel Cloud** | **Keycloak** (Docker, vorkonfigurierter Realm) |
| OCR | **Mistral OCR** | **Docling** |
| LLM + Embeddings | **Mistral** (Chat + Embeddings) | **Ollama** (z. B. Mistral Small / Ministral; Embedding-Modell lokal) |
| CI/CD | **GitHub Actions** | – |

Begründungen kommen als ADRs ins Repo (mind.: Python/FastAPI-Backend, Supabase als Plattform, Mistral Cloud / Ollama lokal, Next.js als Backend-for-Frontend, Spec-Format).

### 5.2 Architekturprinzipien

- **Next.js als Backend-for-Frontend:** Der OIDC-Login läuft serverseitig; **Access-/Refresh-Tokens gelangen nie in den Browser** (HttpOnly-Session-Cookie). Next.js bleibt dünn: Oberfläche, Login, Weiterleitung an FastAPI.
- **FastAPI ist die Sicherheitsschicht:** Token prüfen, Rechte ableiten, pseudonymisieren, Injection filtern, LLM/OCR aufrufen, protokollieren.
- **Austauschbare Anbieter:** OCR, LLM, Embeddings und Identity Provider sind hinter Schnittstellen gekapselt; Umschalten **nur per Konfiguration**, keine Codeänderung.
- **Rechte in der Datenbank:** Supabase **Row Level Security** erzwingt, dass Nutzer und **der KI-Agent** nur Daten ihres Wohnbereichs sehen. Das Backend greift auf Daten **im Namen des Nutzers** zu (nicht mit einem allmächtigen Service-Key), damit RLS greift.
- **Gleiche Architektur öffentlich und lokal**, nur andere Anbieter.

```
Handy/Browser ─▶ Next.js (BFF: OIDC-Login, Session) ─▶ FastAPI ─▶ Mistral / Ollama
                                                         │       ─▶ Mistral OCR / Docling
                                                         └──▶ Supabase (Postgres, pgvector, Storage, RLS)
Identity Provider: Zitadel (öffentlich) / Keycloak (lokal)
```

### 5.3 Rollen [Entscheidung über Mockups]

| Demo-Konto | Sieht | Darf |
|---|---|---|
| Pflegekraft Wohnbereich 1 | Bewohner/Dokumente WB1 | erfassen, freigeben, fragen, Agent-Aktionen bestätigen |
| Pflegekraft Wohnbereich 2 | Bewohner/Dokumente WB2 | wie oben |
| Pflegedienstleitung (PDL) | alle Wohnbereiche + Protokoll | wie oben + Protokoll einsehen |

**Rollenwechsel [Entscheidung]: echtes OIDC.** Auf der Startseite je Rolle ein Knopf, der Logout + regulären OIDC-Login (Authorization Code + PKCE) auf der Login-Seite des Identity Providers startet; die Demo-Zugangsdaten stehen zum Kopieren daneben. Kein Login an OIDC vorbei.

**Agenten-Identität [Entscheidung]: eigenes, eingeschränktes Token.** Für Agent-Aktionen tauscht das Backend das Nutzer-Token per **OAuth 2.0 Token Exchange (RFC 8693)** gegen ein kurzlebiges Agenten-Token (Claims u. a.: handelt im Auftrag von `<Nutzer>`, `act`-Claim für den Agenten, Scopes nur lesen + Wiedervorlage anlegen, Wohnbereich des Nutzers, Gültigkeit wenige Minuten). RLS und Protokoll unterscheiden Mensch und Agent. Unterstützung von Token Exchange in Zitadel und Keycloak beim Spike in Phase 2 prüfen; Rückfall: Backend stellt nach Prüfung des Nutzer-Tokens selbst ein signiertes, eingeschränktes Agenten-JWT mit denselben Claims aus (im ADR dokumentieren).

### 5.4 RAG-Pipeline

**Einlesen:** Foto/PDF → OCR (Markdown) → **Injection-Prüfung** (verdächtige Abschnitte werden markiert und nicht indiziert) → KI-Feldvorschlag → **menschliche Freigabe** → Chunking → Embeddings → pgvector (mit Metadaten).

**Chunking [Entscheidung]:** zuerst **strukturbasiert** (Überschriften/Abschnitte; **Tabellen bleiben ganz**), **Recursive Splitting** als Rückfall für zu lange Abschnitte, mit Überlappung. Lokal kann Doclings HybridChunker genutzt werden; für den Cloud-Weg wird gleichwertiges Verhalten auf dem Mistral-OCR-Markdown gebaut. Startwerte ca. 500–800 Tokens, 10–15 % Überlappung **[Annahme Claude, an Musterdokumenten zu prüfen]**.

**Metadaten pro Chunk:** Bewohner, Wohnbereich, Dokumenttyp, Datum, Seite, Dokument-ID.

**Fragen:** Frage → **Rechte** (nur eigener Wohnbereich, via RLS) → Vektorsuche (optional eingegrenzt auf einen Bewohner) → **Pseudonymisierung** (Namen, Geburtsdaten usw. → Platzhalter wie `Bewohner_A17`, z. B. mit Microsoft Presidio) → LLM → Ausgabe prüfen, zurückübersetzen, **Quellen anhängen**, protokollieren.

### 5.5 Agent

Der Agent ist **kein eigenes Modell**, sondern das Chat-Modell mit Function Calling plus abgesicherter Werkzeugausführung im Backend. Er arbeitet nie mit mehr Rechten als der angemeldete Nutzer.

**Modellrollen [Annahme Claude, Versionen beim Setup prüfen]:** Chat/Agent und Feldvorschläge: Mistral Small (öffentlich) bzw. Mistral Small über Ollama (lokal; bei < 16 GB Speicher Ministral). Injection-Prüfer: Ministral bzw. LLM Guard lokal. Embeddings: mistral-embed bzw. lokales Embedding-Modell. Alles per Konfiguration austauschbar.

**Werkzeuge [Entscheidung]:**

| Werkzeug | Art | Priorität |
|---|---|---|
| Dokumente durchsuchen (RAG) | lesen | Muss |
| Bewohnerakte lesen | lesen | Muss |
| **Medikationsabgleich** (neues Dokument vs. aktuelle Akte: neu / abgesetzt / unverändert) | lesen | Muss — Highlight |
| Offene Wiedervorlagen auflisten | lesen | Muss |
| Wiedervorlage anlegen | schreiben, **nur nach Bestätigung**; gekennzeichnet „vom Agenten angelegt · bestätigt von …“ | Muss |
| Übergabenotiz entwerfen | Entwurf, Speichern nur mit Bestätigung | Kann |
| Rückfrage an Hausarzt entwerfen | Entwurf, wird nie gesendet | Kann |

**Bewusst nicht vorhanden (in der Demo sichtbar gemacht):** Medikation ändern, Daten löschen, Nachrichten nach außen senden, andere Wohnbereiche lesen (verhindert durch Rechte, nicht nur durch Anweisung). Auf entsprechende Bitten lehnt der Agent ab und bietet eine erlaubte Alternative an (z. B. Wiedervorlage).

### 5.5a Prompt-Injection-Schutz (in `apps/api/security/`)

Mehrschichtig, weil kein einzelner Filter zuverlässig ist:

| Schicht | Zeitpunkt | Maßnahme |
|---|---|---|
| 1. Dokument prüfen | Einlesen | Regeln für verdächtige Muster; versteckten Text im PDF erkennen (weiße/winzige Schrift) |
| 2. Klassifikator | Einlesen + Fragen | z. B. LLM Guard (lokal) bzw. kleines Mistral-Modell als Prüfer (öffentlich, falls RAM knapp) |
| 3. Prompt-Aufbau | jede Anfrage | Dokumentinhalte klar als Daten markiert, getrennt vom System-Prompt |
| 4. Minimale Rechte | immer | RLS + Agenten-Rechte + Bestätigungspflicht: Wirkung einer durchgerutschten Injection begrenzt |
| 5. Ausgabe prüfen | vor Antwort | nur erlaubte Quellen, keine Klarnamen |

**Musterquellen:** OWASP Top 10 für LLM-Anwendungen (LLM01); Forschung zu indirekter Injection (Greshake et al. 2023, Microsoft BIPIA); öffentliche Datensätze (z. B. deepset/prompt-injections mit deutschen Beispielen, Lakera Gandalf); garak-Angriffsmodule; **eigene Pflege-Angriffe** (Datenexfiltration, Dosis-Manipulation → abgefangen durch menschliche Freigabe, Agentenmissbrauch → abgefangen durch Bestätigung/Rechte, versteckte weiße Schrift).

**Methodik:** Erkennungsmuster (`apps/api/security/patterns/`) und Testkorpus (`tests/security/corpus/`) sind **strikt getrennt**; der Bericht nennt die Erkennungsrate auf dem Testkorpus. Präparierte Musterdokumente in zwei Varianten: PDF mit versteckter Textebene und sichtbarer, unauffälliger „Hinweis für das KI-System“ (Bild-OCR liest weiße Schrift nicht).

### 5.6 Daten-Lebenszyklus

| Was | Wo | Zugriff |
|---|---|---|
| Originaldatei | Supabase Storage (privat) | eigener WB + PDL |
| OCR-Text, freigegebene Felder | Postgres-Tabellen | eigener WB + PDL |
| Chunks + Vektoren | pgvector | eigener WB + PDL (RLS) |
| Pseudonym-Zuordnung | nur im Backend, nie beim LLM | niemand direkt |
| Protokoll (wer, wann, welches Modell, was blockiert) | Postgres | nur PDL |

**Öffentliche Demo:** **nächtlicher Reset** auf die Musterdaten (GitHub Action); deutlicher Hinweis beim Upload „Bitte keine echten Personendaten hochladen“.

### 5.7 Musterdaten

- Erfundene Bewohner (z. B. „Hr. Muster-Bauer“, „Fr. Beispiel“), Ärzte, Einrichtungen.
- Musterdokumente als PDF/Bild mit Wasserzeichen **„MUSTER“**, im Repo unter `samples/`.
- Mindestens: je ein Arztbrief, Medikationsplan, Überleitungsbogen; **ein präpariertes Dokument mit versteckter Prompt-Injection** (z. B. weiße Schrift).
- Gelbes Banner „MUSTERDATEN · keine echten Personen“ auf allen Bildschirmen.

## 6. Bildschirme [Entscheidung über Mockups]

Untere Navigation (Handy): **Start · Posteingang · Bewohner · Fragen**. Auf Tablet/Desktop dieselben Bereiche nebeneinander.

| Nr. | Bildschirm | Inhalt |
|---|---|---|
| 1 | Start / Anforderungs-Landkarte | Liste der Anforderungen, jeweils mit Sprung zur Stelle in der App; Rollenwechsel |
| 2 | Posteingang | Foto/Upload, Liste eingegangener Dokumente mit Status (wartet, freigegeben, verdächtig) |
| 3 | Prüfen & Freigeben | KI-Vorschläge als Felder, Freigeben / Korrigieren |
| 4 | Fragen | Chat mit Quellen, Hinweis auf Pseudonymisierung und genutztes Modell, Agent-Vorschlag |
| 5 | Angriff erkannt | Anzeige der erkannten versteckten Anweisung, Erklärung des Schutzes |
| 6 | Bewohnerliste | nur eigener Wohnbereich, Hinweise auf neue Änderungen/Wiedervorlagen |
| 7 | Bewohnerakte | Medikation (neu/abgesetzt), Diagnosen, Wiedervorlagen, Dokumente — jeder Eintrag mit Herkunft; „Fragen zu diesem Bewohner“ |
| 8 | Kein Zugriff (andere Rolle) | zeigt, dass weder Nutzer noch Agent fremde Wohnbereiche sehen |

Mockups: `.superpowers/brainstorm/…/content/screens-and-rag.html` und `bewohnerakte.html` (Skizzen, keine Gestaltungsvorgabe).

## 7. Features und Stufen

| Nr. | Feature | Bildschirm | Priorität | Stufe |
|---|---|---|---|---|
| F01 | Login & Rollen (OIDC), Rollenwechsel | 1, 8 | Muss | 1 |
| F02 | Dokument erfassen (Kamera/Upload, OCR) | 2 | Muss | 1 |
| F03 | Felder vorschlagen & freigeben | 3 | Muss | 1 |
| F04 | Bewohnerakte mit Herkunft | 6, 7 | Muss | 1 |
| F05 | Fragen an Dokumente (RAG) mit Quellen | 4 | Muss | 1 |
| F06 | Pseudonymisierung vor dem LLM | 4 | Muss | 2 |
| F07 | Prompt-Injection-Schutz + Testdokument | 5 | Muss | 2 |
| F08 | Agenten-Rechte + bestätigte Aktionen | 4, 7, 8 | Muss | 2 |
| F09 | Anforderungs-Landkarte | 1 | Muss | 1 |
| F10 | Musterdaten, nächtlicher Reset, Upload-Hinweis | alle | Muss | 1 |
| F11 | Docker Compose lokal + CI/CD | – | Muss | 1 |
| F12 | Protokoll für PDL | – | Sollte | 2 |
| F13 | Automatische Sicherheitstests mit Bericht | – | Sollte | 2 |
| F14 | Modellvergleich Cloud vs. lokal (inkl. Chunking-Vergleich) | – | Kann | – |

**Zeitplan [Annahme Claude]:**

| Zeitraum | Ziel |
|---|---|
| 24.–26.10. | Specs, Architektur, Gerüst, Konten (Supabase, Zitadel, Mistral, Koyeb, Vercel) |
| 27.10.–02.11. | **Stufe 1 online** |
| 03.–08.11. | **Stufe 2** |
| 09.–10.11. | Puffer, Feinschliff, **Projektbeschreibung (Phase 9)**, README, Link-Test |
| 11.11. | Bewerbung |

## 8. Spec-getriebenes Vorgehen [Entscheidung]

Format im **Kiro-Stil** (ohne Kiro-IDE). Pro Feature ein Ordner `docs/specs/Fxx-<name>/` mit:

- `requirements.md` — User Stories + Akzeptanzkriterien in **EARS-Form** („WENN …, DANN soll das System …“).
- `design.md` — Umsetzung: Komponenten, Datenmodell, Schnittstellen, Sicherheitsaspekte.
- `tasks.md` — Checkliste; jede Aufgabe verweist auf die Akzeptanzkriterien, die sie erfüllt.

Regel: **Kein Code ohne freigegebene Spec.** Akzeptanzkriterien werden zu Tests.

### 8.1 Teststrategie [Entscheidung]

Testgetrieben: erst Test, dann Code. Jedes EARS-Akzeptanzkriterium hat mindestens einen Test; `tasks.md` verweist darauf.

| Ebene | Werkzeug | Inhalt |
|---|---|---|
| Unit Backend | pytest | Chunking, Pseudonymisierung, Injection-Erkennung, Rechteableitung |
| Unit Web | Vitest | Komponenten, Formularlogik |
| **RLS / Rechte** | pytest gegen lokales Supabase | WB2 sieht nichts aus WB1 — auch nicht über den Agenten |
| Integration | pytest + FastAPI-Testclient | Token → API → DB |
| End-to-End | Playwright (inkl. Handy-Viewport) | Abläufe der Bildschirme 1–8 |
| Sicherheit | Testkorpus + garak/promptfoo | Erkennungsrate, Bericht nach `docs/security/reports/` |

LLM in normalen Tests durch Attrappe ersetzt; kleiner separater Prüfsatz gegen das echte Modell (z. B. „richtige Quelle gefunden?“). Alle Tests laufen in GitHub Actions.

### 8.2 Phasen mit Halte-Punkten [Entscheidung]

Nach **jeder** Phase: Tests grün (Ausgabe zeigen) → **Codex-Review** → Zusammenfassung (gebaut, Codex-Befunde, was umgesetzt wurde) → **Stopp, Bewerber entscheidet über Fortsetzung**.

| Phase | Inhalt | Ergebnis |
|---|---|---|
| 0 | Gerüst, Skills, `CLAUDE.md`, arc42 + ADRs, Konten | lauffähiges leeres Projekt |
| 1 | Specs Stufe 1 (F01–F05, F09–F11) | Freigabe durch Bewerber |
| 2 | Login, Rollen, Datenbank, RLS | Anmelden + Rechte |
| 3 | Erfassen, Freigeben, Bewohnerakte, Musterdaten | Papier → Akte |
| 4 | RAG, Landkarte, Deployment | **Stufe 1 online (Ziel 02.11.)** |
| 5 | Specs Stufe 2 (F06–F08, F12, F13) | Freigabe durch Bewerber |
| 6 | Pseudonymisierung + Injection-Schutz | Sicherheitskern 1 |
| 7 | Agenten-Rechte, Protokoll, Sicherheitstests | Sicherheitskern 2 |
| 8 | Lokaler Betrieb komplett, Feinschliff | technisch fertig |
| 9 | **Projektbeschreibung** (siehe 8.3) | bewerbungsfertig |

### 8.3 Phase 9: Projektbeschreibung [Entscheidung]

Abschließende Beschreibung des gesamten Projekts, erstellt aus dem tatsächlichen Stand (Code, Specs, Architektur, Testberichte) — nicht aus dem Plan. Inhalte:

| Abschnitt | Inhalt |
|---|---|
| Was die Anwendung macht | Szenario, Nutzen für die Pflege, Ablauf in Bildschirmen (mit Screenshots) |
| Bezug zur Stelle | Tabelle „Sie verfügen über …“ → wo in App und Repo umgesetzt |
| Technologie | Stack öffentlich/lokal, Begründungen (Verweis auf ADRs) |
| Architektur | Überblicksdiagramm, Sicherheitsschichten, Datenfluss RAG und Agent |
| Sicherheit & Datenschutz | Rollen, RLS, Agenten-Token, Pseudonymisierungs-Grenze, Injection-Schutz mit gemessener Erkennungsrate, offene Grenzen |
| Vorgehen | spec-getrieben, Tests, Phasen mit Codex-Review |
| Ergebnisse & Ausblick | Cloud vs. lokal (falls gemessen), was im KLARA-Kontext als Nächstes käme |
| Betrieb | Link, Demo-Zugänge, lokaler Start in wenigen Befehlen |

Ablage: `docs/projektbeschreibung.md` als **einzige Quelle**; README verlinkt darauf und fasst sie kurz zusammen. **[Annahme Claude]** Dieselbe Datei wird in der App als Seite **„Über das Projekt“** angezeigt. **[Entscheidung] Sie darf nicht untergehen:** prominente Karte ganz oben auf der Startseite (über der Anforderungs-Landkarte) **und** dauerhaft erreichbarer Eintrag in der Kopfzeile auf jeder Seite (Handy und Desktop). Optional (Kann): 2-seitiger PDF-Steckbrief, automatisch aus derselben Datei erzeugt, falls das Bewerbungsportal Anlagen zulässt.

## 9. Verzeichnisstruktur [Entscheidung]

```
<repo>/
├── README.md                 Link zur Demo, Anforderungs-Landkarte, Schnellstart lokal
├── CLAUDE.md                 Arbeitsregeln für Claude Code
├── docs/
│   ├── architecture/
│   │   ├── architecture.md   arc42 (schlank: Kontext, Bausteine, Laufzeit, Verteilung, Querschnitt/Sicherheit, Entscheidungen)
│   │   ├── adr/              Architecture Decision Records
│   │   └── diagrams/         C4-Diagramme (Mermaid)
│   ├── specs/Fxx-<name>/     requirements.md, design.md, tasks.md
│   ├── security/
│   │   ├── threat-model.md   orientiert an OWASP Top 10 für LLM-Anwendungen
│   │   └── reports/          Ergebnisse der Sicherheitstests
│   └── superpowers/specs/    dieses Design-Dokument
├── apps/
│   ├── web/                  Next.js, Tailwind, shadcn/ui, PWA
│   └── api/                  FastAPI
├── supabase/
│   ├── migrations/           Tabellen, pgvector, RLS-Policies
│   └── seed/                 Musterbewohner
├── samples/                  Musterdokumente (inkl. präpariertes)
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.local-llm.yml   Ollama + Docling
│   └── keycloak/             Realm mit Rollen
└── .github/workflows/        CI/CD, Sicherheitstests, Keep-alive, nächtlicher Reset
```

**Technische Architektur** lebt an **einer** Stelle: `docs/architecture/architecture.md` (+ ADRs, Diagramme).

**Projekt-Skills [Entscheidung, aus `brainstorming_prompt.md`]:** im Projekt installieren: `npx skills add shadcn/ui` und `npx skills add supabase/agent-skills`.

## 10. Bekannte Risiken

| Risiko | Gegenmaßnahme |
|---|---|
| Supabase pausiert nach 1 Woche ohne Aktivität; API auf Vercel hat Kaltstarts (ADR 0011) | Keep-alive-Ping per GitHub Action; Hinweis „Demo startet …“ in der App |
| Backend-Hosting (bezahlte Kleininstanz) nicht verfügbar | Alternative Hetzner oder Render (Frankfurt) |
| Token Exchange (RFC 8693) im IdP nicht/teilweise verfügbar | Rückfall siehe 5.3; früh in Phase 2 klären |
| Zitadel-Token und Supabase-RLS zusammenbringen (Supabase erwartet eigene JWTs) | früh als technischer Spike in F01 klären (z. B. Backend stellt nach Prüfung des OIDC-Tokens ein Supabase-kompatibles JWT mit Rolle/Wohnbereich aus, oder Supabase Third-Party-Auth, falls Zitadel unterstützt) |
| Docling braucht viel RAM | nur lokal; öffentlich Mistral OCR |
| Python-Erfahrung des Bewerbers gering | Claude schreibt den Großteil; Code bewusst lesbar und kommentiert; Bewerber muss ihn im Gespräch erklären können |
| Stufe 2 (Sicherheitskern) wird nicht fertig | Stufe 1 bis 02.11. online; Stufe 2 vor Feinschliff priorisieren |
| Kostenlose Kontingente (Mistral Experiment-Plan, Zitadel, Qdrant) ändern sich | Limits beim Anlegen der Konten prüfen |

## 11. Dem Umsetzer überlassen

- Konkrete Bibliotheken für Injection-Erkennung (z. B. LLM Guard, eigene Heuristik + LLM-Klassifikator) und Sicherheitstests (z. B. garak, promptfoo).
- RAG-Bibliothek (LlamaIndex, LangChain oder schlank selbst gebaut).
- Datenmodell im Detail, API-Design, Teststrategie im Detail.
- Konkretes Ollama-Modell und lokales Embedding-Modell.
- Visuelle Gestaltung im Rahmen von shadcn/ui (sachlich, gut lesbar, Farbe z. B. Petrol).
- Endgültiger Projekt-/Repo-Name.

## 12. Von Claude getroffene Festlegungen (bitte prüfen)

- „4 Stunden“ als 4 h pro Tag interpretiert; Zeitplan und Stufen darauf aufgebaut.
- Rollen: zwei Wohnbereiche + PDL.
- Modellwahl (Mistral Small / Ministral / mistral-embed) und lokaler Rückfall auf Ministral bei wenig Speicher.
- Nächtlicher Reset und Upload-Warnhinweis.
- **Neutraler Name und Hinweis im Footer:** „Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt“; keine Logos der Hochschule.
- Chunk-Größen als Startwerte.
- Next.js als BFF (Tokens nie im Browser).

- **Spec-Freigabe gebündelt:** Specs werden pro Stufe gesammelt freigegeben (Stufe 1 bis 26.10., Stufe 2 bis 02.11.), damit die Review-Zeit des Bewerbers nicht zum Engpass wird. „4 h/Tag“ schließt diese Reviews ein.
- **Pseudonymisierungs-Grenze:** OCR braucht das Originalbild — im Cloud-Modus sieht Mistral OCR daher Rohdaten. Das ist genau das Argument für den lokalen Modus (Docling) und wird im Bedrohungsmodell und in der App offen benannt. **Nach der OCR** wird der Text pseudonymisiert, **bevor** Feldextraktion, Embeddings und Chat-LLM ihn sehen. Die Zuordnung zum Bewohner läuft über Metadaten (Bewohner-ID), nicht über Namen im Embedding; Suche „nach Name“ wird im Backend auf die Bewohner-ID aufgelöst. Aussage der Demo: „Außer der OCR sieht kein Cloud-Modell identifizierende Daten; im lokalen Modus gar keines.“ Ab Stufe 2 (F06); in Stufe 1 laufen nur Musterdaten durch.
- **Gemeinsamer Datenstand für Besucher:** alle Besucher teilen die Demo-Konten bis zum nächtlichen Reset (keine Sandbox pro Besucher). Schutz vor Kosten/Missbrauch: Upload-Limit pro Sitzung und globale Tagesobergrenze für Mistral-Aufrufe; danach freundlicher Hinweis, Musterdokumente bleiben nutzbar.

## 13. Ergebnis nach Freigabe

1. Umsetzungsplan (superpowers:writing-plans).
2. **Kick-off-Prompt** (`docs/kickoff-prompt.md`): ein Prompt, mit dem eine neue Claude-Code-Sitzung das Projekt aufsetzt — Skills installieren, Verzeichnisstruktur und `CLAUDE.md` anlegen, arc42-Gerüst + ADRs schreiben, Specs F01–F11 im Kiro-Format erstellen, dann Stufe 1 umsetzen.
