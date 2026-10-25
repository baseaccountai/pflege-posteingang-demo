# F03 – Felder vorschlagen & freigeben: Aufgaben

- [ ] **1. Migration Akte** — `F03-AC8`
  - [ ] RLS-Tests: WB2 kann nicht in WB1 schreiben; `delete` verboten → rot → Migration → grün · Commit `feat(db): add medication, diagnosis and follow-up tables`
- [ ] **2. Medikationsabgleich** — `F03-AC7`
  - [ ] Tabellentests `tests/extraction/test_medication_diff.py` (neu, geändert, unverändert, abgesetzt, Groß/Klein, Leerzeichen) → rot → `medication_diff.py` → grün · Commit
- [ ] **3. LLM-Schnittstelle + Fabrik** — `F03-AC13`
  - [ ] Tests: Fabrik nach `LLM_PROVIDER`; Mistral-Adapter mit `respx` (Schema übergeben, Fehler → `LlmUnavailable`) → rot → grün · Commit
- [ ] **4. Extraktion** — `F03-AC1`, `F03-AC2`, `F03-AC3`
  - [ ] Tests mit Attrappe: gültig; ungültig → 1 Retry → leer + Hinweis; Medikament ohne Fundstelle markiert → rot → `service.py` → grün · Commit
- [ ] **5. Bewohner-Abgleich** — `F03-AC5`, `F03-AC6`
  - [ ] Tests: eindeutig, mehrdeutig, nur im fremden WB vorhanden (→ kein Vorschlag) → rot → grün · Commit
- [ ] **6. Endpunkte Vorschlag/Freigabe/Verwerfen** — `F03-AC8`, `F03-AC9`, `F03-AC10`, `F03-AC11`
  - [ ] Integrationstests inkl. paralleler Doppel-Freigabe und fehlender Bestätigung (422) → rot → grün · Commit `feat(api): add suggestion review and approval`
- [ ] **7. Prüfansicht** — `F03-AC4`, `F03-AC5`, `F03-AC12`
  - [ ] Vitest + Playwright (desktop + mobile) → rot → grün · Commit `feat(web): add review and approval screen`
