# F05 – Fragen an Dokumente (RAG): Aufgaben

- [x] **1. Chunker** — `F05-AC2`, `F05-AC3`
  - [x] `tests/rag/test_chunker.py` mit Muster-Markdown (Arztbrief mit Abschnitten, Medikationsplan mit Tabelle, sehr langer Abschnitt, Riesentabelle) → rot → `chunker.py` → grün · Commit `feat(api): add structure-aware chunker`
- [x] **2. Embedding-Schnittstelle + Mistral-Adapter** — `F05-AC13` · Tests (`respx`, Batch, Dimension) → rot → grün · Commit
- [x] **3. Migration `chunks` + `match_chunks`** — `F05-AC4`, `F05-AC5`
  - [x] RLS-Tests: WB2 findet keine WB1-Chunks; Bewohnerfilter wirkt; anderes Modell ignoriert; WB2 kann WB1-Chunks nicht löschen → rot → Migration → grün · Commit `feat(db): add vector chunks with ward isolation`
- [ ] **3a. Vorberechnete Seed-Chunks (F10 Aufgabe 3)** — `F10-AC1`, `F10-AC6` · nach Aufgabe 3: `apps/api/scripts/build_seed_chunks.py` einmalig mit echtem Mistral (Schlüssel des Bewerbers, eigenes Terminal), `supabase/seed/chunks.jsonl` committen, Reset lädt sie; Test: Laden ohne Netz → Chunks vorhanden, `indexing_status = done` · Commit
- [x] **4. Indexer (Auslöser F03-AC11)** — `F05-AC1`, `F05-AC1a` · Integrationstests: Freigabe → Chunks mit Seite/Metadaten; erneute Indizierung ersetzt atomar; Embedding-Fehler → `failed` + Neuversuch → rot → grün · Commit
- [x] **5. Retrieval + Namensauflösung** — `F05-AC6`, `F05-AC7` · Tests: fremder und unbekannter Name → identische Antwort, LLM-Attrappe nicht aufgerufen → rot → grün · Commit
- [x] **6. Antwort mit Quellen** — `F05-AC8`, `F05-AC8a`, `F05-AC9`, `F05-AC10`, `F05-AC12` · Tests Prompt-Aufbau, Zitatprüfung (gültig/fehlend/erfunden), Längenlimit, 429 → rot → grün · Commit `feat(api): answer questions with sources`
- [x] **7. Fragen-UI** — `F05-AC5`, `F05-AC8`, `F05-AC10`, `F05-AC11`
  - [x] Vitest + Playwright (Frage aus Akte; Rollenwechsel → leer; verspätete Antwort nach Wechsel unsichtbar) → rot → grün · Commit `feat(web): add question screen with sources`
- [ ] **8. Realtest** — 5 Fragen gegen echtes Mistral, Schwellwert kalibrieren, Ergebnis notieren
