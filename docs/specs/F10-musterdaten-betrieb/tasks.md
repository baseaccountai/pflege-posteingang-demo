# F10 – Musterdaten, Reset, Hinweise: Aufgaben

- [ ] **1. Musterdokument-Generator** — `F10-AC2`, `F10-AC3` · Tests → rot → `samples/generate.py` → grün; Dateien erzeugen und committen · Commit `feat(samples): add generated sample documents`
- [ ] **2. Seeds** — `F10-AC1` · DB-Test: nach Seed 6 Bewohner, je WB 3, Akteneinträge mit Herkunft → rot → Seed-SQL → grün · Commit
- [ ] **3. Vorberechnete Chunks** — `F10-AC6` · Skript mit echtem Mistral einmalig ausführen (Bewerber-Schlüssel), `chunks.jsonl` committen; Test: Laden ohne Netz → Chunks vorhanden · Commit
- [ ] **4. Quote** — `F10-AC9` · DB-Tests inkl. Parallelität → rot → Migration `usage_counters` + `app.consume_quota` → grün · Commit `feat(db): add atomic daily quotas`
- [ ] **5. Reset-Skript** — `F10-AC5`, `F10-AC7` · DB-Tests (Upload weg, Rollback bei Fehler) → rot → `reset_demo.py` → grün · Commit
- [ ] **6. Workflows Reset + Keep-alive + `/health/ready`** — `F10-AC5`, `F10-AC8` · API-Test `/health/ready` → rot → grün; Workflows; nach Deployment manuell auslösen · Commit `ci: add nightly reset and keep-alive`
- [ ] **7. Hinweise in der App** — `F10-AC10`, `F10-AC11`, `F10-AC12` · Vitest + Playwright mit Attrappe → rot → grün · Commit `feat(web): show startup and quota notices`
- [ ] **8. Banner-Regression** — `F10-AC4` · Playwright über alle Hauptseiten → grün · Commit
