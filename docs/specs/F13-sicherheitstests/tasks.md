# F13 – Automatische Sicherheitstests mit Bericht: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [x] **1. Korpus** — `F13-AC1`, `F13-AC2` · Schema-Test zuerst (rot bei leerem Korpus), dann Einträge aus drei Quellen · Commit `test(security): add prompt injection corpus`
- [x] **2. Messung in der CI** — `F13-AC3` · erste Messung legt `thresholds.json` fest (Wert im Commit genannt) · Commit
- [x] **3. Szenario-Tests** — `F13-AC4` · nach F06–F08 · Commit · `tests/security/test_scenarios.py`: beide Angriffs-PDFs → Befunde, kein Klarname an irgendein Modell; Agent liest freigegebenen Brief mit Anweisung → nur offener Vorschlag, Anweisung vor der Indizierung herausgeschnitten (Gegenprobe: Indexer auf ungeprüften Text → Test rot); Auftrag zu WB2 → Antwort wie für niemanden, kein Modellaufruf; kein Klarname an das Agenten-Modell
- [x] **4. Bericht** — `F13-AC5`, `F13-AC6` · Runner + Make-Ziel; Bewerber führt `make security-report` aus; Bericht committen · Commit `docs(security): add injection detection report` · erledigt 31.10.2026: `docs/security/reports/2026-10-31-injection.md` (Regeln 12,7 %, Prüfmodell 88,8 %, beide 89,6 %; Fehlalarme 11,3 %)
- [x] **5. Verweise** — `F13-AC7`, `F13-AC8` · Landkarte, `/projekt`, Bedrohungsmodell · Commit · `SECURITY_REPORT` setzt der Bericht-Commit (Aufgabe 4)
- [x] **6. Korpus und Bericht für Anfragen** — `F13-AC9` (ergänzt 02.11.2026) · `tests/security/requests/anfragen.jsonl` (26 harmlos, 21 Angriffe), `scripts/request_report.py`, `make request-report [ANWEISUNG=dokument]` · gemessen 02.11.2026 (`ministral-8b-latest`): Dokument-Anweisung 21/21 Angriffe erkannt, Fehlalarme 30,8 % (8/26); Anfrage-Anweisung 21/21, Fehlalarme 3,8 % (1/26, „Lösche die erledigte Wiedervorlage …“) · `docs/security/reports/2026-11-02-anfragen*.md`
