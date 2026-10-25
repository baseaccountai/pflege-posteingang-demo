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
| Indexer | `rag/indexer.py` | Chunks + Metadaten speichern; idempotent je Dokument (alte Chunks ersetzen) |
| Retrieval | `rag/retrieval.py` | Namensauflösung, `match_chunks`, Schwellwert `RAG_MIN_SIMILARITY` (Start 0,35, an Musterdaten kalibrieren) |
| Antwort | `rag/answer.py` | Prompt-Aufbau mit nummerierten Quellen `[Q1]…`, Antwort muss Quellen zitieren; Quellen ohne Zitat werden nicht angezeigt |
| Fragen-UI | `apps/web/src/app/fragen/page.tsx` | Chat (Client-State), Bewohner-Filter (`?bewohner=`), Quellen-Chips, Modellhinweis |

## Datenmodell

Migration `<ts>_f05_chunks.sql`: `create extension vector`; Tabelle `chunks` (siehe Datenmodell), Index **HNSW** `vector_cosine_ops`; RLS `select/insert` eigener WB; Funktion

```sql
app.match_chunks(query vector(1024), p_resident uuid, p_limit int, p_min_sim float)
  returns table (id uuid, document_id uuid, resident_id uuid, doc_type doc_type,
                 document_date date, page int, heading text, content text, similarity float)
  language sql stable security invoker
```

Die Dimension 1024 gilt für `mistral-embed`; der lokale Betrieb wählt ein Embedding-Modell mit derselben Dimension oder eine eigene Spalte (Entscheidung Phase 8, F14).

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
| LLM09 Misinformation | Quellenpflicht | AC8 |
| Verlauf nach Rollenwechsel | nur Seiten-State | AC11 |
| LLM10 Kosten | Längenlimit, Quote | AC12 |

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest | AC2, AC3 (Chunker mit Muster-Markdown: Tabelle bleibt ganz, Überlappung, Kopfzeile wiederholt), AC9 (Prompt-Aufbau), AC13 |
| RLS | pytest + lokales Supabase | AC4, AC5 (`match_chunks` als WB2 liefert keine WB1-Chunks) |
| Integration | pytest + Embedding/LLM-Attrappen (deterministische Vektoren) | AC1, AC6, AC7 (fremd vs. unbekannt identisch, LLM nicht aufgerufen), AC8, AC12 |
| Unit Web | Vitest | AC8 (Quellen-Chips), AC10, AC11 (kein Storage-Zugriff) |
| End-to-End | Playwright | Frage aus Akte heraus; Rollenwechsel → Verlauf leer |
| Realtest (klein) | echtes Mistral, 5 Fragen an Musterdaten | richtige Quelle unter den Top 3; Bericht in `docs/security/reports/` nicht nötig, Ergebnis in Spec-Notiz |
