# F06 – Pseudonymisierung vor dem LLM: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [x] **1. Pseudonymisierer und Regeln** — `F06-AC2`, `F06-AC3`, `F06-AC6` · Tabellentests (Anreden, Titel, Bindestrich, Datumsformate, Telefon, Versichertennr., Adresse, Rückübersetzung) → rot → grün · Commit `feat(api): add pseudonymizer`
- [x] **2. Migration `residents.pseudonym` + `app.pseudonym_directory()`** — `F06-AC3`, `F06-AC8` · RLS-Tests (nur die Verzeichnis-Spalten; nur `api_gateway`, kein Fach-Principal, kein `anon`; `api_gateway` darf keine andere `app`-Funktion) · Seed mit festen Codes · Commit `feat(db): add resident pseudonyms`
- [x] **3. Gateway als einzige Tür** — `F06-AC1`, `F06-AC10` · Architekturtest (kein direkter Anbieter-Import außerhalb des Gateways) + Abbruchtest · Commit `feat(api): route all model calls through the privacy gateway`
- [x] **4. Feldvorschlag (F03) über das Gateway** — `F06-AC6` · Integrationstest: Fake-LLM sieht keinen Klarnamen, Belege werden nach Rückübersetzung geprüft, Bewohner-Zuordnung (F03) unverändert · Commit
- [x] **5. Indizierung und Fragen (F05) über das Gateway** — `F06-AC1`, `F06-AC4`, `F06-AC5`, `F06-AC7` · Integrationstests; Antwort enthält `sent_to_model`; Architekturtest (nur das Gateway erzeugt Modelle, auch in Skripten) · Commit
- [ ] **6. Seed-Chunks neu** — Skript bettet pseudonymisiert ein (Test vorhanden, braucht lokale DB mit Seed); Bewerber führt `make db-start` und `make seed-chunks` aus · Commit der neuen `04_chunks.sql`
- [ ] **7. Oberfläche** — `F06-AC7`, `F06-AC9`, `F06-AC11` · Vitest + Playwright · Commit `feat(web): show what the model saw`
- [ ] **8. Realtest** — `make rag-probe` erneut: Antworten mit Platzhaltern weiterhin richtig, Schwelle `RAG_MIN_SIMILARITY` prüfen; Ergebnis notieren
