# F12 – Protokoll für die Pflegedienstleitung: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [x] **1. Tabelle, Trigger + `app.log_event`** — `F12-AC2` bis `F12-AC6`, `F12-AC8`, `F12-AC9` · Migration, Rolle `audit_owner`, RLS-Tests · Commit `feat(db): add append-only audit log` · Trigger an `agent_proposals` folgen mit F08 Aufgabe 3 (die Tabelle entsteht dort)
- [x] **2. Ereignisse schreiben** — `F12-AC1`, `F12-AC3`, `F12-AC8` · `app/audit.py`; Aufrufe in Pipeline (F02/F03), Fragen (F05), F06/F07-Blockierungen, Agent (F08 – sobald vorhanden); Integrationstests · Commit · Agent-Ereignisse folgen mit F08 Aufgaben 4–5
- [x] **3. Route `GET /audit`** — `F12-AC6` · Tests PDL/Pflegekraft · Commit
- [ ] **4. Seite `/protokoll` + Navigation** — `F12-AC6`, `F12-AC7` · Vitest + Playwright · Reset leert Tabelle (F10-Test erweitern) · Commit `feat(web): add audit log for the care manager`
