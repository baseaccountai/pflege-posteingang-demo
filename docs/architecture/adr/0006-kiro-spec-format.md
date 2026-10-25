# ADR 0006: Spec-Format im Kiro-Stil

Status: angenommen · Datum: 23.10.2026

## Kontext
Die Entwicklung soll spec-getrieben und im Repo nachvollziehbar sein. Akzeptanzkriterien sollen direkt zu Tests werden.

## Entscheidung
Pro Feature ein Ordner `docs/specs/Fxx-<name>/` im **Kiro-Stil** (ohne Kiro-IDE):
- `requirements.md`: User Stories + Akzeptanzkriterien in **EARS-Form** mit IDs `Fxx-ACn`.
- `design.md`: Komponenten, Datenmodell, Schnittstellen, Sicherheitsaspekte, Tests je Ebene.
- `tasks.md`: TDD-Checkliste, jede Aufgabe mit Verweis auf `Fxx-ACn`.

Regel: **Kein Code ohne freigegebene Spec.** Jedes Kriterium hat mindestens einen Test.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Nur Issues/Tickets | Anforderungen nicht versioniert neben dem Code |
| Gherkin/BDD | zusätzliches Werkzeug; EARS reicht und bleibt lesbar |

## Konsequenzen
+ Nachvollziehbar von Anforderung über Test bis Code.
− Mehr Schreibaufwand vor dem Code; Freigaben gebündelt pro Stufe.
