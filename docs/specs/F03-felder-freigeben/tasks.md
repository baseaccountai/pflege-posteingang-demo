# F03 – Felder vorschlagen & freigeben: Aufgaben

- [x] **1. Migration Akte** — `F03-AC8`
  - [x] RLS-Tests: WB2 kann nicht in WB1 schreiben; kein Verweis auf WB1-Bewohner/-Dokument; `delete` verboten; fachliche Spalten freigegebener Dokumente unveränderlich, `indexing_status` änderbar; `resident_id` einmalig `null` → Bewohner erlaubt, danach nicht mehr änderbar → rot → Migration → grün · Commit `feat(db): add medication, diagnosis and follow-up tables`
- [ ] **2. Medikationsabgleich** — `F03-AC7`
  - [ ] Tabellentests `tests/extraction/test_medication_diff.py` (neu, geändert, unverändert, abgesetzt, Groß/Klein, Leerzeichen) → rot → `medication_diff.py` → grün · Commit
- [ ] **3. LLM-Schnittstelle + Fabrik** — `F03-AC13`
  - [ ] Tests: Fabrik nach `LLM_PROVIDER`; Mistral-Adapter mit `respx` (Schema übergeben, Fehler → `LlmUnavailable`) → rot → grün · Commit
- [ ] **4. Extraktion** — `F03-AC1`, `F03-AC2`, `F03-AC3`
  - [ ] Tests mit Attrappe: gültig; ungültig → 1 Retry → leer + Hinweis; Werte ohne Fundstelle (jeder Feldtyp) markiert und nicht vorbelegt → rot → `service.py` → grün · Commit
- [ ] **5. Bewohner-Abgleich** — `F03-AC5`, `F03-AC6`
  - [ ] Tests: eindeutig, mehrdeutig, nur im fremden WB vorhanden (→ kein Vorschlag) → rot → grün · Commit
- [ ] **6. Endpunkte Vorschlag/Freigabe/Verwerfen** — `F03-AC8`, `F03-AC8a`, `F03-AC9`, `F03-AC10`, `F03-AC11`
  - [ ] Integrationstests: parallele Doppel-Freigabe; Freigabe gegen Verwerfen; Freigabe im falschen Status; zweiter Plan desselben Bewohners → 409 mit neuem Abgleich; fehlende Bestätigung → 422; Ereignisse geschrieben → rot → grün · Commit `feat(api): add suggestion review and approval`
- [ ] **7. Prüfansicht** — `F03-AC4`, `F03-AC5`, `F03-AC6a`, `F03-AC12`
  - [ ] Vitest + Playwright (desktop + mobile): falscher Bewohner vorgeschlagen → anderen wählen → Bestätigung zurückgesetzt, Abgleich neu → bestätigen → freigeben → rot → grün · Commit `feat(web): add review and approval screen`
