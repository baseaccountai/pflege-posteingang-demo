# F13 – Automatische Sicherheitstests mit Bericht: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [x] **1. Korpus** — `F13-AC1`, `F13-AC2` · Schema-Test zuerst (rot bei leerem Korpus), dann Einträge aus drei Quellen · Commit `test(security): add prompt injection corpus`
- [x] **2. Messung in der CI** — `F13-AC3` · erste Messung legt `thresholds.json` fest (Wert im Commit genannt) · Commit
- [ ] **3. Szenario-Tests** — `F13-AC4` · nach F06–F08 · Commit · Teil 1 erledigt (`tests/security/test_scenarios.py`: beide Angriffs-PDFs → Befunde, kein Klarname an irgendein Modell); offen: Agent-Szenarien mit F08
- [ ] **4. Bericht** — `F13-AC5`, `F13-AC6` · Runner + Make-Ziel; Bewerber führt `make security-report` aus; Bericht committen · Commit `docs(security): add injection detection report` · Runner + Make-Ziel erledigt; offen: Lauf durch den Bewerber, Bericht committen
- [ ] **5. Verweise** — `F13-AC7`, `F13-AC8` · Landkarte, `/projekt`, Bedrohungsmodell · Commit
