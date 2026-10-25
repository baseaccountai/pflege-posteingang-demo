# F10 – Musterdaten, Reset, Hinweise: Aufgaben

- [ ] **1. Musterdokument-Generator** — `F10-AC2`, `F10-AC3` · Tests → rot → `samples/generate.py` → grün; Dateien erzeugen und committen · Commit `feat(samples): add generated sample documents`
- [ ] **2. Seeds** — `F10-AC1` · DB-Test: nach Seed 6 Bewohner, je WB 3, Akteneinträge mit Herkunft und Ereignissen → rot → Seed-SQL → grün · Commit
- [ ] **3. Vorberechnete Chunks** — `F10-AC6` · Skript einmalig mit echtem Mistral (Schlüssel des Bewerbers), `chunks.jsonl` committen; Test: Laden ohne Netz → Chunks vorhanden · Commit
- [ ] **4. Kontingente** — `F10-AC10` · DB-Tests (Parallelität, ungültige Mengen, `anon`, Limit nicht änderbar) → rot → Migration `usage_counters`, `quota_limits`, `app.consume_quota` → grün · Commit `feat(db): add atomic daily quotas`
- [ ] **5. Kostenrechnung** — `F10-AC11` · Preise aus dem Mistral-Konto in ADR 0003; Unit-Tests der Längenbegrenzung → rot → grün · Commit
- [ ] **6. Wartungsmodus + Reset-Skript** — `F10-AC5`, `F10-AC6`, `F10-AC7`, `F10-AC8` · DB-/API-Tests → rot → `system_state`, Flag-Prüfung, `reset_demo.py` → grün · Commit `feat(ops): add transactional nightly reset`
- [ ] **7. Workflows Reset + Keep-alive + `/health/ready`** — `F10-AC5`, `F10-AC9` · Unit-Test Zeitprüfung, API-Test `/health/ready` → rot → grün; nach Deployment manuell auslösen · Commit `ci: add nightly reset and keep-alive`
- [ ] **8. Musterakte** — `F10-AC14` · Vitest + Übereinstimmungstest mit Seed → rot → `make sample-record`, `/muster` → grün · Commit
- [ ] **9. Hinweise in der App** — `F10-AC12`, `F10-AC13`, `F10-AC15` · Vitest + Playwright mit Attrappe → rot → grün · Commit `feat(web): show startup, quota and maintenance notices`
- [ ] **10. Layout-Regression** — `F10-AC4` · Playwright über alle Seitentypen (desktop + mobile) → grün · Commit
