# ADR 0003: Mistral öffentlich, Ollama und Docling lokal

Status: angenommen · Datum: 23.10.2026 · Versionen werden in Task 0.7 ergänzt

## Kontext
Die Demo braucht OCR, ein Chat-/Agentenmodell mit Function Calling, einen kleinen Prüfer und Embeddings. Europäische Anbieter werden bevorzugt. Die Stelle wünscht Erfahrung mit lokalen Modellen; das Projekt KLARA vergleicht Cloud- und lokale Modelle.

## Entscheidung
| Rolle | Öffentlich | Lokal |
|---|---|---|
| OCR | Mistral OCR | Docling |
| Chat/Agent, Feldvorschläge | Mistral Small | Mistral Small über Ollama (bei < 16 GB Speicher Ministral) |
| Injection-Prüfer | Ministral – **nur auf bereits pseudonymisiertem Text** | LLM Guard |
| Embeddings | mistral-embed | lokales Embedding-Modell |

Umschalten **nur per Konfiguration** (`LLM_PROVIDER`, `OCR_PROVIDER`). Öffentlich läuft kein lokales Modell.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| OpenAI / Anthropic | nicht europäisch |
| Nur lokal | öffentlicher Betrieb mit GPU sprengt das Budget |
| Nur Cloud | kein Beleg für lokale Modelle; Cloud-OCR sieht Rohdaten |

## Konsequenzen
+ Europäischer Anbieter, nutzungsabhängige Kosten, Tagesobergrenze im Backend.
+ Lokaler Modus: kein Cloud-Modell sieht identifizierende Daten.
− Im Cloud-Modus sieht Mistral OCR Rohdaten (im Bedrohungsmodell und in der App offen benannt).

## Offen (Task 0.7)
- Prüfen und festhalten: **keine Trainingsnutzung der Eingaben** im gewählten Mistral-Plan.
- Aktuelle Modellversionen von Mistral Small, Ministral, mistral-embed, Mistral OCR.
