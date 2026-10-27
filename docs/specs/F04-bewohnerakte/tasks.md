# F04 – Bewohnerakte: Aufgaben

- [x] **1. Voraussetzung prüfen** — F03-Migration enthält Herkunfts- und Erledigt-Spalten (kein eigener Commit)
- [x] **2. `GET /residents` mit Zählern** — `F04-AC1`, `F04-AC2`
  - [x] Integrationstests (WB1, WB2, PDL; „neu“ 6 vs. 8 Tage; überfällige Wiedervorlage) → rot → grün · Commit
- [x] **3. `GET /residents/{id}/record`** — `F04-AC3`, `F04-AC4`, `F04-AC5`, `F04-AC6`, `F04-AC9`, `F04-AC10`
  - [x] Integrationstests inkl. Ereignisfolge angesetzt→geändert→abgesetzt, Agenten-Eintrag (per Seed) und 404 fremd/unbekannt → rot → grün · Commit
- [x] **4. `POST /follow-ups/{id}/done`** — `F04-AC8` · Test → rot → grün · Commit
- [x] **5. Herkunft-Komponente** — `F04-AC5`, `F04-AC6` · Vitest → rot → grün · Commit
- [x] **6. Seiten Liste + Akte** — `F04-AC1`–`F04-AC10`
  - [x] Playwright: Liste je Rolle; Akte zeigt Herkunft; „Fragen zu diesem Bewohner“ öffnet `/fragen?bewohner=<id>`; fremde ID → Bildschirm 8 → rot → grün · Commit `feat(web): add resident list and record with provenance`
