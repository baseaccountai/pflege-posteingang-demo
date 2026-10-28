# F05 – Fragen an Dokumente (RAG): Design

## Ablauf

```
Indizierung (nach Freigabe, Hintergrund):
  ocr_markdown → chunker.split() → EmbeddingProvider.embed(batch) → insert chunks (as_principal)
Frage:
  Frage → Name→resident_id (RLS) → embed(Frage) → app.match_chunks(embedding, resident_id, 6, min_sim) [security invoker → RLS]
        → keine Treffer? „Keine Treffer in deinem Wohnbereich.“
        → Prompt (System | <dokumente>…</dokumente> | Frage) → LLM → Antwort + Quellen-IDs → Quellen auflösen
```

Bewusst **schlank selbst gebaut** statt LlamaIndex/LangChain (Design 11 überlässt die Wahl): ca. 300 Zeilen, jede Stufe einzeln testbar und im Gespräch erklärbar.

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Chunker | `apps/api/app/rag/chunker.py` | Markdown-Abschnitte (Überschriften `#`–`###`), Tabellenblöcke atomar, rekursiver Rückfall mit Überlappung; Tokenzählung über einfache Schätzung (Zeichen/4), austauschbar |
| Embeddings | `apps/api/app/providers/embeddings/{base,mistral,ollama}.py` | `embed(texts) -> list[list[float]]`, `dimension`; Mistral `mistral-embed` (1024) |
| Indexer | `rag/indexer.py` | je Dokument in **einer** Transaktion unter `as_principal`: alte Chunks löschen, neue einfügen, `indexing_status = done`; Fehler → `failed` (AC1a); Seite aus `documents.ocr_pages` |
| Retrieval | `rag/retrieval.py` | Namensauflösung, `match_chunks`, Schwellwert `RAG_MIN_SIMILARITY` (Start 0,35; kalibriert 28.10.2026 mit mistral-embed auf 0,72 – siehe Aufgabe 8) |
| Antwort | `rag/answer.py` | Prompt-Aufbau mit nummerierten Quellen `[Q1]…[Q6]`; Antwortprüfung: mindestens ein Zitat, alle Zitate ⊆ abgerufene Quellen, sonst Ersatzantwort (AC8a); `max_tokens` 600 |
| Fragen-UI | `apps/web/src/app/fragen/page.tsx` | Chat (Client-State), Bewohner-Filter (`?bewohner=`), Quellen-Chips, Modellhinweis |

## Datenmodell

Migration `<ts>_f05_chunks.sql`: `create extension vector`; Tabelle `chunks` (siehe Datenmodell) mit zusammengesetztem Fremdschlüssel auf das Dokument; **kein** Näherungsindex – bei wenigen hundert Chunks ist exakte Suche schnell genug und verliert unter Wohnbereichs-/Bewohnerfiltern keine Treffer; RLS `select/insert/delete` eigener WB (Chunks sind abgeleitete Daten); Funktion

```sql
app.match_chunks(query vector(1024), p_model text, p_resident uuid, p_limit int, p_min_sim float)
  returns table (id uuid, document_id uuid, resident_id uuid, doc_type doc_type,
                 document_date date, page int, heading text, content text, similarity float)
  language sql stable security invoker
```

Die Dimension 1024 gilt für `mistral-embed`. Vektoren verschiedener Modelle sind nicht vergleichbar, auch bei gleicher Dimension: `match_chunks` filtert auf `embedding_model`, ein Modellwechsel erfordert `make reindex` (Phase 8, F14).

## Schnittstellen (API)

| Methode | Pfad | Request | Response |
|---|---|---|---|
| POST | `/questions` | `{question (≤ 500), resident_id?}` | `{answer, sources[{document_id, doc_type, document_date, resident_name, page}], model, no_hits: bool}` · 429 Quote |

## Sicherheitsaspekte

| Risiko (OWASP LLM) | Maßnahme | AC |
|---|---|---|
| LLM08 Vector Weaknesses – fremde Chunks | RLS auf `chunks`, `security invoker` | AC4 |
| Existenz-Leck über Namen | gleiche Antwort ohne LLM-Aufruf | AC6, AC7 |
| LLM01 indirekte Injection | Daten-Begrenzer, nur freigegebene Dokumente indiziert (Mensch hat gesehen) | AC1, AC9 |
| LLM09 Misinformation | Quellenpflicht mit Zitatprüfung, Ersatzantwort | AC8, AC8a |
| Verlauf nach Rollenwechsel | nur Seiten-State, harter Seitenwechsel verwirft laufende Anfragen | AC11 |
| LLM10 Kosten | Längenlimit, Quote | AC12 |

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest | AC2, AC3 (Chunker mit Muster-Markdown: Tabelle bleibt ganz, Überlappung, Kopfzeile wiederholt), AC8/AC8a (Zitatprüfung: gültig, fehlend, `[Q9]` erfunden), AC9 (Prompt-Aufbau), AC13 |
| RLS | pytest + lokales Supabase | AC4, AC5 (`match_chunks` als WB2 liefert keine WB1-Chunks; Chunks eines anderen Modells werden ignoriert), AC1 (Neuindizierung ersetzt, WB2 kann WB1-Chunks nicht löschen) |
| Integration | pytest + Embedding/LLM-Attrappen (deterministische Vektoren) | AC1, AC1a (Embedding-Fehler → `failed`, Neuversuch), AC6, AC7 (fremd vs. unbekannt identisch, LLM nicht aufgerufen), AC8, AC12 |
| Unit Web | Vitest | AC8 (Quellen-Chips), AC10, AC11 (kein Storage-Zugriff) |
| End-to-End | Playwright | Frage aus Akte heraus; Rollenwechsel → Verlauf leer; Frage als WB1 absenden, sofort Rolle wechseln → keine WB1-Antwort sichtbar; als WB2 nach WB1-Bewohner fragen → „Keine Treffer in deinem Wohnbereich.“ |
| Realtest (klein) | echtes Mistral, 5 Fragen an Musterdaten | richtige Quelle unter den Top 3; Bericht in `docs/security/reports/` nicht nötig, Ergebnis in Spec-Notiz |
