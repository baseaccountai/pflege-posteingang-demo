# Pflege-Posteingang – Projektbeschreibung

> **Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt.**
> Bewerbung auf Stelle Nr. 479 (Wissenschaftliche Mitarbeit Web Engineering). Alle Personen und
> Dokumente sind erfundene Musterdaten. Stand: 01.11.2026.

Demo: <https://pflege-posteingang-demo.vercel.app> · Repository: <https://github.com/baseaccountai/pflege-posteingang-demo>

## Was die Anwendung macht

In Pflegeeinrichtungen kommen Arztbriefe, Medikationspläne und Überleitungsbögen weiterhin auf
Papier an und werden von Hand in die Dokumentation übertragen. Der **Pflege-Posteingang** ist der
digitale Eingang dafür, mit generativer KI und einer Sicherheitsarchitektur, die man in der
Oberfläche sehen und ausprobieren kann:

| Schritt | Was passiert | Wo die KI begrenzt wird |
|---|---|---|
| 1. Erfassen | Foto oder PDF hochladen; OCR macht daraus Text | Prüfung auf versteckte Anweisungen, bevor ein Sprachmodell den Text sieht |
| 2. Prüfen und Freigeben | Die KI schlägt Bewohner, Diagnosen, Medikation und Wiedervorlagen vor; die API gleicht jeden Wert mit der wörtlichen Textstelle im Dokument ab, das Original steht daneben; ein Medikationsabgleich zeigt neu, geändert, abgesetzt | **Ein Mensch gibt frei.** Ohne Bestätigung des Bewohners geht nichts in die Akte |
| 3. Bewohnerakte | Freigegebene Daten mit Herkunft: aus welchem Dokument, von wem freigegeben | Row Level Security: jede Pflegekraft sieht nur ihren Wohnbereich |
| 4. Fragen (RAG) | Fragen an die freigegebenen Dokumente; Antworten nur mit geprüften Quellenzitaten | Das Modell sieht keine Namen, nur Platzhalter wie `Bewohner_K42` |
| 5. Agent | Ein Agent liest mit den Rechten der Pflegekraft und schlägt Wiedervorlagen vor | Eigenes Agenten-Token; gespeichert wird erst nach „Bestätigen“ |
| 6. Protokoll | Die Pflegedienstleitung sieht, wer wann welches Modell genutzt hat und was blockiert wurde | Protokoll nur für die PDL, Akteur setzt die Datenbank |

Die Bilder stammen aus der lokalen Testumgebung mit Modell-Attrappe (daher „fake-llm“ als
Modellname); in der öffentlichen Demo arbeitet an derselben Stelle Mistral.

![Startseite mit Projektkarte, Anforderungs-Landkarte und Rollenwahl](assets/projekt/start.png)

![Posteingang: ein Medikationsplan bereit zur Prüfung, ein präparierter Brief als verdächtig markiert](assets/projekt/posteingang.png)

![Prüfen und Freigeben: KI-Vorschlag und Medikationsabgleich gegen die Akte (unverändert, geändert, neu, abgesetzt)](assets/projekt/pruefen.png)

![Angriff erkannt: die unsichtbare weiße Schrift im PDF wird sichtbar gemacht](assets/projekt/angriff-erkannt.png)

![Bewohnerakte: Medikation, Diagnosen, Wiedervorlagen und Dokumente, jeder Eintrag mit Herkunft](assets/projekt/bewohnerakte.png)

![Fragen an die Dokumente: Antwort mit Quelle und dem, was das Modell tatsächlich gesehen hat](assets/projekt/fragen.png)

![Agent: Vorschlag einer Wiedervorlage, erst nach Bestätigung gespeichert](assets/projekt/agent.png)

![Kein Zugriff: Wohnbereich 2 öffnet die Akte aus Wohnbereich 1](assets/projekt/kein-zugriff.png)

![Bewohnerakte auf dem Handy](assets/projekt/handy-bewohnerakte.png)

## Bezug zur Stelle

**„Sie verfügen über …“** – wo es in der Demo zu sehen ist (dieselbe Zuordnung steht als
Anforderungs-Landkarte auf der Startseite):

| Anforderung | Umsetzung | In der App | Im Repository |
|---|---|---|---|
| Softwarearchitektur, Web-Backend (Python/TypeScript) | Next.js als Backend-for-Frontend (TypeScript), FastAPI (Python) als Sicherheitsschicht, Postgres; arc42 mit 12 ADRs | – | [Architektur](architecture/architecture.md), [`apps/api/`](../apps/api/), [`apps/web/`](../apps/web/) |
| Anbindung von LLMs über APIs | Mistral OCR, Mistral Small (Feldvorschläge, Antworten, Agent), Ministral (Prüfmodell), mistral-embed; Anbieter per Konfiguration austauschbar, Tageskontingente | Posteingang | [`providers/`](../apps/api/app/providers/), [`extraction/`](../apps/api/app/extraction/) |
| RAG und agentenbasierte KI | Strukturbewusstes Chunking, Vektorsuche nur im eigenen Wohnbereich, Antworten nur mit geprüften Zitaten; Agent mit Function Calling, fünf Werkzeugen und Bestätigungspflicht | Fragen, Agent | [`rag/`](../apps/api/app/rag/), [`agent/`](../apps/api/app/agent/) |
| IT- und API-Sicherheit, OAuth 2.0/OIDC | OIDC-Login (Code + PKCE) über den BFF, Tokens nie im Browser, Zugriff im Namen des Nutzers unter RLS, Agenten-Token per Token Exchange (RFC 8693) | Rollenwahl, Bewohner | [`auth/`](../apps/api/app/auth/), [Migrationen](../supabase/migrations/), [ADR 0012](architecture/adr/0012-agent-token.md) |
| *wünschenswert:* lokale Sprachmodelle | Komplett lokaler Betrieb mit `make up-local`: Ollama (`qwen3:8b`, `bge-m3`), Docling und Keycloak, ohne Cloud-Dienst; nur per Konfiguration umgeschaltet | – | [`ollama.py`](../apps/api/app/providers/llm/ollama.py) |
| *wünschenswert:* Docker, CI/CD | Docker-Images für Web und API; GitHub Actions: Tests, Secret-Scan, Deployment nur bei grüner CI, nächtlicher Reset | – | [Workflows](../.github/workflows/), [`infra/`](../infra/) |
| *wünschenswert:* Sicherheitsrisiken von LLM-Anwendungen | Bedrohungsmodell nach OWASP Top 10 für LLM-Anwendungen, fünf Schichten gegen Prompt-Injection, gemessen auf einem Testkorpus | Posteingang (Musterdokumente mit Angriff) | [Bedrohungsmodell](security/threat-model.md), [`security/`](../apps/api/app/security/) |

**Aufgaben der Stelle** – was die Demo davon im Kleinen vorwegnimmt:

| Aufgabe | In der Demo |
|---|---|
| Sicherheitsrisiken generativer KI untersuchen (Prompt-Injection, RAG, Agenten) | Bedrohungsmodell, präparierte Musterdokumente, Angriffskorpus mit 134 Angriffen und Bericht |
| Systemarchitektur: Schnittstellen, Rollen- und Rechtekonzepte, modulare KI-Modelle | Rollen aus OIDC-Claims, RLS je Wohnbereich, Agent mit eigener Identität, Anbieter hinter Schnittstellen |
| Sicherheitskonzepte unter DSGVO und EU AI Act, Vergleich Cloud und lokal | Pseudonymisierung vor jedem Modell, ehrlich benannte Grenze bei der OCR, Hinweis „KI-Antwort, bitte prüfen“, Protokoll. Eine Einordnung nach AI Act und der Messvergleich Cloud gegen lokal stehen noch aus |
| Sicherheitskomponenten spezifizieren, implementieren, testen | Jede Funktion als Spec mit Akzeptanzkriterien, testgetrieben umgesetzt, Sicherheitstests in der CI |

## Technologie

| Rolle | Öffentlich | Lokal | Begründung |
|---|---|---|---|
| Web-App | Next.js 16, Tailwind, shadcn/ui, PWA auf Vercel (`fra1`) | Docker | [ADR 0004](architecture/adr/0004-nextjs-bff.md), [ADR 0008](architecture/adr/0008-minimal-service-worker.md) |
| Backend | Python 3.12, FastAPI auf Vercel (`fra1`) | Docker | [ADR 0001](architecture/adr/0001-python-fastapi-backend.md), [ADR 0011](architecture/adr/0011-api-on-vercel.md) |
| Daten, Vektoren, Dateien | Supabase (Postgres, pgvector, RLS), Region Irland | Supabase lokal | [ADR 0002](architecture/adr/0002-supabase-platform.md), [ADR 0010](architecture/adr/0010-files-in-postgres.md) |
| Login (OIDC) | Zitadel Cloud | Keycloak bzw. Test-IdP | [ADR 0005](architecture/adr/0005-zitadel-public-keycloak-local.md) |
| OCR | Mistral OCR | Docling | [ADR 0003](architecture/adr/0003-mistral-cloud-ollama-local.md) |
| Sprachmodelle | Mistral Small, Ministral 8B, mistral-embed | Ollama (z. B. Qwen3 8B, bge-m3) | [ADR 0003](architecture/adr/0003-mistral-cloud-ollama-local.md) |
| CI/CD | GitHub Actions | – | – |

Welcher Anbieter läuft, entscheidet allein die Konfiguration (`OCR_PROVIDER`, `LLM_PROVIDER`,
`OIDC_ISSUER` …), nicht der Code. Für Tests gibt es zu jedem Anbieter eine Attrappe.

## Architektur

![Architektur: Browser, Next.js als BFF, FastAPI als Sicherheitsschicht, Supabase mit RLS, Identity Provider und KI-Anbieter](assets/projekt/architektur.svg)

Grundsätze ([arc42-Dokument](architecture/architecture.md)):

- **Next.js ist nur Backend-for-Frontend.** Der Browser bekommt ein Sitzungs-Cookie, die Tokens
  liegen verschlüsselt (AES-256-GCM) in Postgres ([ADR 0009](architecture/adr/0009-server-side-sessions.md)).
- **FastAPI ist die Sicherheitsschicht.** Sie prüft jedes Token selbst und ruft Modelle nur über
  ein einziges Modell-Tor auf. Ein Architekturtest stellt sicher, dass kein anderes Modul einen
  Anbieter direkt nutzt.
- **Die Rechte liegen in der Datenbank.** Die API greift im Namen des Nutzers oder des Agenten zu
  (`set local role` + Claims je Transaktion, [ADR 0007](architecture/adr/0007-db-access-on-behalf-of-user.md)).
  Row Level Security trennt die Wohnbereiche auch dann, wenn die API einen Fehler hätte. Der
  Service-Schlüssel dient nur Seed und Reset.

**Datenfluss beim Einlesen:** Datei → OCR → Prüfung auf versteckten Text und Regeln (lokal, ohne
Cloud-Modell) → Pseudonymisierung → Prüfmodell → Feldvorschlag → Freigabe durch einen Menschen →
Chunking (Überschriften, Tabellen ganz, sonst rekursiv mit ca. 600 Tokens und 12 % Überlappung)
→ Embeddings → pgvector mit Wohnbereich, Bewohner, Dokumenttyp, Datum und Seite. Verdächtige
Abschnitte werden nicht indiziert.

**Datenfluss bei einer Frage:** Frage → Prüfung auf Angriffe → Vektorsuche unter RLS → Namen durch
Platzhalter ersetzt → Modell → Ausgabe geprüft (nur Zitate aus den gefundenen Quellen, keine Links
oder Bilder) → Platzhalter zurückübersetzt → Antwort mit Quellen → Protokoll.

**Datenfluss beim Agenten:** Token der Pflegekraft → Token Exchange bei Zitadel → Agenten-Token
(`sub` = Pflegekraft, `act` = Agent) → höchstens vier Werkzeugschritte, fünf Modellaufrufe,
60 Sekunden → Vorschlag (15 Minuten gültig) → „Bestätigen“ durch die Pflegekraft → erst dann legt
der Agent die Wiedervorlage an.

## Sicherheit und Datenschutz

**Rollen und Rechte**

| Wer | Sieht | Darf |
|---|---|---|
| Pflegekraft WB1 / WB2 | Bewohner und Dokumente des eigenen Wohnbereichs | erfassen, freigeben, fragen, Agent beauftragen und bestätigen |
| Pflegedienstleitung | beide Wohnbereiche und das Protokoll | wie oben, dazu Protokoll |
| Agent | höchstens, was die beauftragende Pflegekraft sieht | lesen, Wiedervorlage **vorschlagen**; anlegen erst nach Bestätigung |

Ein fremder Bewohner und einer, den es nicht gibt, ergeben dieselbe Antwort. So verrät die Demo
nicht einmal, dass es einen Datensatz gibt. Das gilt auch für den Agenten: Fragt man ihn nach
einer Person aus dem anderen Wohnbereich, antwortet er, ohne ein Modell aufzurufen.

**Was der Agent nicht kann:** Medikation ändern, Daten löschen, Nachrichten nach außen senden,
andere Wohnbereiche lesen. Diese Aktionen gibt es nicht als Werkzeug, und die Datenbank würde sie
dem Agenten-Token auch nicht erlauben. Steht in einem Dokument eine Anweisung an die KI, entsteht
daraus höchstens ein offener Vorschlag, den ein Mensch verwerfen kann.

**Pseudonymisierung:** Bevor ein Sprachmodell einen Text sieht, ersetzt die API Namen und
Geburtsdaten aller Bewohner, weitere Personen nach Anrede oder Titel, Telefonnummern,
E-Mail-Adressen, Versichertennummern und Adressen durch Platzhalter. Die Zuordnung bleibt im
Speicher der API. Das Modell-Tor prüft unmittelbar vor dem Aufruf noch einmal: Steht noch ein
Klarname im Text, wird das Modell nicht aufgerufen. Bei jeder Antwort kann man aufklappen, was
das Modell tatsächlich gesehen hat.

**Prompt-Injection: fünf Schichten**, weil kein einzelner Filter zuverlässig ist:

| Schicht | Maßnahme |
|---|---|
| 1. Dokument prüfen | Regeln für typische Angriffsmuster; versteckter Text im PDF (weiße oder winzige Schrift) |
| 2. Prüfmodell | Ministral bewertet jeden Abschnitt (nur pseudonymisierten Text) |
| 3. Prompt-Aufbau | Dokumentinhalte als markierte Daten, getrennt von den Anweisungen |
| 4. Minimale Rechte | RLS, eingeschränktes Agenten-Token, Bestätigungspflicht |
| 5. Ausgabe prüfen | nur Zitate aus erlaubten Quellen, keine Klarnamen, keine Links |

**Gemessen** auf einem Testkorpus mit 134 Angriffen (deepset/prompt-injections, eigene Angriffe
nach BIPIA-Muster, eigene Pflege-Angriffe) und 62 harmlosen Pflegetexten
([Bericht vom 31.10.2026](security/reports/2026-10-31-injection.md)):

| Schicht | Erkennungsrate | Fehlalarmrate |
|---|---|---|
| Regeln allein | 12,7 % (17/134) | 0,0 % (0/62) |
| Prüfmodell (`ministral-8b-latest`) | 88,8 % (119/134) | 11,3 % (7/62) |
| beide zusammen | 89,6 % (120/134) | 11,3 % (7/62) |

Erkennungsmuster und Testkorpus liegen getrennt. Die CI prüft bei jedem Push, dass die Regeln
nicht schlechter werden.

**Offene Grenzen, ehrlich benannt** ([Bedrohungsmodell](security/threat-model.md)):

- Die Cloud-OCR sieht das Originaldokument mit Namen; nur der lokale Betrieb mit Docling vermeidet das.
- Etwa jeder zehnte Angriff kommt durch die Erkennung, am häufigsten Rollenspiele (Jailbreaks,
  64,7 % erkannt). Die Schichten 3 bis 5 begrenzen dann die Wirkung: Nichts geht ohne Freigabe in
  die Akte, und der Agent kann nur vorschlagen.
- 11,3 % Fehlalarme bei harmlosen Texten: Ein markiertes Dokument wird nicht gelöscht, sondern
  einem Menschen zur Prüfung gezeigt.
- Die Pseudonymisierung arbeitet mit dem Verzeichnis der Bewohner und mit Regeln. Ein Name ohne
  Anrede, der nicht im Verzeichnis steht, kann durchrutschen.

## Vorgehen

- **Spec vor Code:** 13 Funktionen (F01–F13), jede mit Anforderungen, Design und Aufgaben im
  Kiro-Stil ([ADR 0006](architecture/adr/0006-kiro-spec-format.md)), zusammen 167
  Akzeptanzkriterien in EARS-Form („WENN …, DANN soll das System …“). Code entstand erst nach
  Freigabe der Spec ([`docs/specs/`](specs/)).
- **Testgetrieben:** Zu jedem Akzeptanzkriterium gibt es mindestens einen Test, und jeder Test
  wurde zuerst rot gesehen. Stand: 920 API-Tests (pytest, davon 422 gegen eine echte
  Postgres-Datenbank mit RLS), über 330 Web-Unit-Tests (Vitest) und 84 End-to-End-Abläufe
  (Playwright), jeweils auf Desktop und Handy. Sprachmodelle sind in den Tests Attrappen. Echte
  Modelle prüft ein kleiner, getrennter Satz von Realtests.
- **Phasen mit Halte-Punkt:** Jede Phase endet mit grünen Tests, einem unabhängigen Code-Review
  (Codex) und einer Entscheidung des Bewerbers, ob und wie es weitergeht.
- **KI-gestützt entwickelt:** Der Code entstand mit Claude Code als Coding-Agent. Feste Regeln
  ([`CLAUDE.md`](../CLAUDE.md)) legten dabei Specs, Tests, Reviews und Sicherheitsgrenzen fest.
  Der Bewerber hat jede Spec und jede Phase freigegeben.

## Ergebnisse und Ausblick

**Ergebnisse:**

- Die Sicherheitsarchitektur ist in einer laufenden Anwendung sichtbar: Rollen, RLS, Agenten-Token
  und Pseudonymisierung kann man ausprobieren, ebenso Angriffe über die Musterdokumente im Posteingang.
- Messwerte statt Behauptungen: Erkennungs- und Fehlalarmrate je Schicht und Kategorie.
- Kosten: Tageskontingente begrenzen die öffentliche Demo auf höchstens 0,50 € Mistral-Kosten pro Tag.

- Komplett lokal läuft dieselbe Anwendung ohne Cloud-Dienst (Keycloak, Docling, Ollama). Auf einem
  Laptop ohne GPU ist das langsam: `qwen3:8b` schreibt etwa 1,3 Tokens/s, ein Feldvorschlag dauert
  rund 13 Minuten. Der lokale Modus zeigt, dass es geht und dass kein Text den Rechner verlässt;
  für den Alltag bräuchte er eine GPU oder ein kleineres Modell.

**Noch offen:** ein gemessener Vergleich der Qualität von Cloud- und lokalen Modellen
(Feldvorschläge, Antworten, Erkennungsrate).

**Was im KLARA-Kontext als Nächstes käme:**

| Thema | Nächster Schritt |
|---|---|
| Vergleich Cloud und lokal | Gleicher Korpus und gleiche Fragen gegen Mistral und lokale Modelle; Ergebnis als Entscheidungshilfe für Einrichtungen |
| Pseudonymisierung | Erkennung von Namen per NER (z. B. Presidio) zusätzlich zum Verzeichnis; Messung der Trefferquote |
| Agenten | Feinere Delegation (Scopes je Werkzeug), Widerruf laufender Aufträge, Prüfung weiterer Werkzeuge |
| Regulierung | Einordnung nach EU AI Act und DSGVO-Folgenabschätzung gemeinsam mit Pflegepraxis und Medizinethik |
| Praxiserprobung | Rückmeldungen von Pflegekräften zu Verständlichkeit von Belegen, Warnungen und Bestätigungen |

## Betrieb

**Öffentliche Demo:** <https://pflege-posteingang-demo.vercel.app>. Auf der Startseite gibt es
einen Knopf je Rolle. Die Zugangsdaten sind absichtlich öffentlich und werden alle 15 Minuten
zurückgesetzt:

| Rolle | Benutzername | Passwort |
|---|---|---|
| Pflegekraft WB1 | `pflege-wb1` | `Pflege-WB1-Demo!` |
| Pflegekraft WB2 | `pflege-wb2` | `Pflege-WB2-Demo!` |
| Pflegedienstleitung | `pdl` | `Pflege-PDL-Demo1!` |

Ohne Anmeldung zeigt `/muster` eine Musterakte. Jede Nacht um 3 Uhr werden alle Daten auf die
Musterdaten zurückgesetzt. Uploads sind auf fünf pro Sitzung begrenzt. **Bitte keine echten
Personendaten hochladen.** Schläft die Datenbank (kostenloser Tarif), zeigt die App „Demo
startet gerade …“.

**Lokal**, ohne Konto und ohne Schlüssel (Supabase, Web, API, Test-IdP, Attrappen für OCR und LLM):

```bash
make setup     # einmalig: Abhängigkeiten und Playwright-Browser
make up-test   # alles starten
make smoke     # prüft Startseite, API mit Datenbank und Test-IdP
make test      # Unit-Tests API und Web
make e2e       # End-to-End auf Desktop und Handy
```

Mit `make up` laufen echte Anbieter und der IdP aus der `.env`.

**Komplett lokal**, ohne Cloud-Dienst (Keycloak, Docling, Ollama auf dem eigenen Rechner, etwa 10 GB
freier Arbeitsspeicher):

```bash
ollama pull qwen3:8b && ollama pull bge-m3
make up-local      # anmelden wie öffentlich, z. B. pflege-wb1
make smoke-local   # prüft alle Dienste und ruft die echten Modelle einmal auf
```

Weitere Befehle und gemessene Laufzeiten stehen in der [README](../README.md).
