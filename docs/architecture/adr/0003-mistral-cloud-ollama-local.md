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

## Kosten (F10-AC11, Stand 28.10.2026)

Öffentliche Listenpreise, aus Drittquellen recherchiert und teils widersprüchlich – gerechnet wird mit dem **höchsten** gefundenen Wert, US-Dollar als Euro gezählt (1 $ < 1 €). **Vor der Bewerbung mit der Preisseite im Mistral-Konto abgleichen.**

| Modell | Preis (konservativ) |
|---|---|
| Mistral OCR | 4,00 $ je 1000 Seiten |
| Mistral Small (Eingabe / Ausgabe) | 0,15 $ / 0,60 $ je 1 Mio. Tokens |
| mistral-embed | 0,10 $ je 1 Mio. Tokens |

| Posten | Annahme | Tagesmaximum |
|---|---|---|
| OCR | 50 Seiten | 0,200 € |
| LLM | 100 Aufrufe × teuerster Aufruf (Feldvorschlag: ≤ 7753 Tokens Eingabe bei 3 Zeichen/Token, ≤ 1500 Ausgabe = 0,00206 €) | 0,206 € |
| Embeddings | 500 Chunks × 800 Tokens | 0,040 € |
| **Summe** | | **0,446 € ≤ 0,50 €** |

Die Rechnung steht als Code in `apps/api/app/costs.py`; der Test `tests/rls/test_daily_cost.py` liest die Limits aus der Datenbank und schlägt fehl, sobald ein Limit oder eine Längenbegrenzung die 0,50 € überschreitet. Zusätzlich: Monatslimit 10 € im Mistral-Konto.

## Offen (Task 0.7)
- Prüfen und festhalten: **keine Trainingsnutzung der Eingaben** im gewählten Mistral-Plan.
- Aktuelle Modellversionen von Mistral Small, Ministral, mistral-embed, Mistral OCR.
