# ADR 0001: Python/FastAPI als Backend

Status: angenommen · Datum: 23.10.2026

## Kontext
Die Sicherheitsschicht (Token-Prüfung, Pseudonymisierung, Injection-Erkennung, LLM/OCR-Anbindung) braucht ein Backend. Die Stelle nennt Web-Backend-Entwicklung in Python oder TypeScript. Werkzeuge wie Microsoft Presidio, LLM Guard, Docling und die Mistral-SDKs sind in Python am besten verfügbar.

## Entscheidung
Das Backend wird in **Python mit FastAPI** gebaut (Paketverwaltung `uv`, Tests `pytest`, Lint `ruff`). Next.js bleibt dünn (BFF, siehe ADR 0004).

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Alles in Next.js/TypeScript | Presidio, LLM Guard und Docling sind Python-Bibliotheken (Stand Recherche 10/2026, zu prüfen); Sicherheitslogik vermischt mit Oberfläche |
| Django | schwerer, ORM/Admin hier nicht nötig |
| Node (NestJS) separat | gleiche Bibliotheksnachteile wie oben |

## Konsequenzen
+ Direkter Zugang zum Python-Ökosystem für KI-Sicherheit; OpenAPI automatisch.
+ Belegt die im Profil des Bewerbers fehlende Python-Erfahrung.
− Zwei Sprachen im Repo; Code muss bewusst lesbar und kommentiert sein.
