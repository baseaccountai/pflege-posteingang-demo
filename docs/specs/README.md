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

## Ablauf

1. Ordner aus [`_template/`](_template/) kopieren.
2. Specs einer Stufe schreiben → Codex-Review auf Widersprüche/Lücken → **Freigabe durch den Bewerber** (gebündelt pro Stufe).
3. Erst dann Code: Test → Fehlschlag → Code → grün → Commit.
4. Status unten aktualisieren.

## Status

| Nr. | Feature | Priorität | Stufe | Status |
|---|---|---|---|---|
| F01 | Login & Rollen (OIDC), Rollenwechsel | Muss | 1 | Entwurf |
| F02 | Dokument erfassen (Kamera/Upload, OCR) | Muss | 1 | Entwurf |
| F03 | Felder vorschlagen & freigeben | Muss | 1 | Entwurf |
| F04 | Bewohnerakte mit Herkunft | Muss | 1 | Entwurf |
| F05 | Fragen an Dokumente (RAG) mit Quellen | Muss | 1 | Entwurf |
| F06 | Pseudonymisierung vor dem LLM | Muss | 2 | offen |
| F07 | Prompt-Injection-Schutz + Testdokument | Muss | 2 | offen |
| F08 | Agenten-Rechte + bestätigte Aktionen | Muss | 2 | offen |
| F09 | Anforderungs-Landkarte | Muss | 1 | Entwurf |
| F10 | Musterdaten, nächtlicher Reset, Upload-Hinweis | Muss | 1 | Entwurf |
| F11 | Docker Compose lokal + CI/CD | Muss | 1 | Entwurf |
| F12 | Protokoll für PDL | Sollte | 2 | offen |
| F13 | Automatische Sicherheitstests mit Bericht | Sollte | 2 | offen |
| F14 | Modellvergleich Cloud vs. lokal | Kann | – | offen |

Status-Werte: `offen` · `Entwurf` · `freigegeben` · `in Umsetzung` · `fertig`
