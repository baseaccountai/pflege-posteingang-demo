# Feature-Specs

Format im Kiro-Stil (siehe [ADR 0006](../architecture/adr/0006-kiro-spec-format.md)). Pro Feature ein Ordner `Fxx-<name>/` mit:

| Datei | Inhalt |
|---|---|
| `requirements.md` | User Stories + Akzeptanzkriterien in EARS-Form, IDs `Fxx-ACn` |
| `design.md` | Komponenten, Datenmodell, Schnittstellen, Sicherheit, Tests je Ebene |
| `tasks.md` | TDD-Checkliste; jede Aufgabe verweist auf `Fxx-ACn` |

## Ablauf

1. Ordner aus [`_template/`](_template/) kopieren.
2. Specs einer Stufe schreiben → Codex-Review auf Widersprüche/Lücken → **Freigabe durch den Bewerber** (gebündelt pro Stufe).
3. Erst dann Code: Test → Fehlschlag → Code → grün → Commit.
4. Status unten aktualisieren.

## Status

| Nr. | Feature | Priorität | Stufe | Status |
|---|---|---|---|---|
| F01 | Login & Rollen (OIDC), Rollenwechsel | Muss | 1 | offen |
| F02 | Dokument erfassen (Kamera/Upload, OCR) | Muss | 1 | offen |
| F03 | Felder vorschlagen & freigeben | Muss | 1 | offen |
| F04 | Bewohnerakte mit Herkunft | Muss | 1 | offen |
| F05 | Fragen an Dokumente (RAG) mit Quellen | Muss | 1 | offen |
| F06 | Pseudonymisierung vor dem LLM | Muss | 2 | offen |
| F07 | Prompt-Injection-Schutz + Testdokument | Muss | 2 | offen |
| F08 | Agenten-Rechte + bestätigte Aktionen | Muss | 2 | offen |
| F09 | Anforderungs-Landkarte | Muss | 1 | offen |
| F10 | Musterdaten, nächtlicher Reset, Upload-Hinweis | Muss | 1 | offen |
| F11 | Docker Compose lokal + CI/CD | Muss | 1 | offen |
| F12 | Protokoll für PDL | Sollte | 2 | offen |
| F13 | Automatische Sicherheitstests mit Bericht | Sollte | 2 | offen |
| F14 | Modellvergleich Cloud vs. lokal | Kann | – | offen |

Status-Werte: `offen` · `Entwurf` · `freigegeben` · `in Umsetzung` · `fertig`
