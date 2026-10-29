# Feature-Specs

Format im Kiro-Stil (siehe [ADR 0006](../architecture/adr/0006-kiro-spec-format.md)). Pro Feature ein Ordner `Fxx-<name>/` mit:

| Datei | Inhalt |
|---|---|
| `requirements.md` | User Stories + Akzeptanzkriterien in EARS-Form, IDs `Fxx-ACn` |
| `design.md` | Komponenten, Datenmodell, Schnittstellen, Sicherheit, Tests je Ebene |
| `tasks.md` | TDD-Checkliste; jede Aufgabe verweist auf `Fxx-ACn` |

Gemeinsames Datenmodell aller Features: [`datenmodell.md`](datenmodell.md) · Alle Umgebungsvariablen: [`konfiguration.md`](konfiguration.md).

## Umsetzungsreihenfolge Stufe 1 (vertikal zuerst)

| Schritt | Phase | Inhalt | Ziel |
|---|---|---|---|
| 1 | 2 | F01 Spike → Login öffentlich, Rollen, RLS | Anmelden + Rechte |
| 2 | 3 | F02 → F03 → F04, dazu F10 (Seeds, Kontingente) | Papier → Akte durchgängig |
| 3 | 4 | F05 RAG, F09 Landkarte, F11 PWA + Deployment, F10 Reset/Hinweise | **online bis 02.11.** |

Bei Zeitnot wird zuerst F11-PWA-Feinschliff verschoben, nie Rechte- oder Sicherheitskriterien.

## Umsetzungsreihenfolge Stufe 2

Leitfaden ist ein Rundgang von fünf Minuten: (1) präpariertes Dokument → „Angriff erkannt“ (F07), (2) Frage mit „Das hat das KI-Modell gesehen“ (F06), (3) Agent gleicht Medikation ab und schlägt eine Wiedervorlage vor, Bestätigung (F08), (4) Agent lehnt Dosisänderung und WB2 ab (F08), (5) PDL-Protokoll und Testbericht (F12, F13).

| Schritt | Phase | Inhalt |
|---|---|---|
| 0 | 6 | F08 Aufgabe 1: Spike Token Exchange (Bewerber schaltet Zitadel-Beta ein) – Ergebnis vor allem anderen, weil RLS und Werkzeuge darauf aufbauen |
| 1 | 6 | F06 (Gateway zuerst, alle Modellaufrufe laufen danach hindurch) → F07 |
| 2 | 7 | F08 (RLS mit Bestätigung vor Werkzeugen und Oberfläche) → F12 → F13 |

**Bei Zeitnot (nach Rückfrage):** zuerst F13-Korpusgröße und Bericht kürzen, dann F12-Filter, dann die Oberfläche „Das hat das KI-Modell gesehen“ vereinfachen – nie RLS, Bestätigungspflicht, Prüfung vor dem Feldvorschlag oder die Pseudonymisierung selbst.

## Ablauf

1. Ordner aus [`_template/`](_template/) kopieren.
2. Specs einer Stufe schreiben → Codex-Review auf Widersprüche/Lücken → **Freigabe durch den Bewerber** (gebündelt pro Stufe).
3. Erst dann Code: Test → Fehlschlag → Code → grün → Commit.
4. Status unten aktualisieren.

## Status

| Nr. | Feature | Priorität | Stufe | Status |
|---|---|---|---|---|
| F01 | Login & Rollen (OIDC), Rollenwechsel | Muss | 1 | freigegeben |
| F02 | Dokument erfassen (Kamera/Upload, OCR) | Muss | 1 | freigegeben |
| F03 | Felder vorschlagen & freigeben | Muss | 1 | freigegeben |
| F04 | Bewohnerakte mit Herkunft | Muss | 1 | freigegeben |
| F05 | Fragen an Dokumente (RAG) mit Quellen | Muss | 1 | freigegeben |
| F06 | Pseudonymisierung vor dem LLM | Muss | 2 | freigegeben 29.10.2026 |
| F07 | Prompt-Injection-Schutz + Testdokument | Muss | 2 | freigegeben 29.10.2026 |
| F08 | Agenten-Rechte + bestätigte Aktionen | Muss | 2 | freigegeben 29.10.2026 |
| F09 | Anforderungs-Landkarte | Muss | 1 | freigegeben |
| F10 | Musterdaten, nächtlicher Reset, Upload-Hinweis | Muss | 1 | freigegeben |
| F11 | Docker Compose lokal + CI/CD | Muss | 1 | freigegeben |
| F12 | Protokoll für PDL | Sollte | 2 | freigegeben 29.10.2026 |
| F13 | Automatische Sicherheitstests mit Bericht | Sollte | 2 | freigegeben 29.10.2026 |
| F14 | Modellvergleich Cloud vs. lokal | Kann | – | offen |

Status-Werte: `offen` · `Entwurf` · `freigegeben` · `in Umsetzung` · `fertig`
