# F07 – Prompt-Injection-Schutz + Testdokumente: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [x] **1. Präparierte Musterdokumente** — `F07-AC12` · `samples/generate.py` erweitern (weiße/winzige Textebene; sichtbarer „Hinweis für das KI-System“); Test: Text liegt in der PDF-Textebene, ist aber weiß bzw. < 3 pt · Commit `feat(samples): add two documents with prompt injection`
- [x] **2. Versteckten Text erkennen** — `F07-AC2` · Tests mit beiden Musterdokumenten, normalem Arztbrief (kein Befund) und Tr3-OCR-Ebene · Commit `feat(api): detect hidden text in PDFs`
- [x] **3. Muster + Korpus-Trennung** — `F07-AC3`, `F07-AC13` · TOML-Regeln (Python liest TOML ohne Zusatzpaket), Abschnittsbildung, Trennungstest · Commit
- [x] **4. Klassifikator** — `F07-AC4` · Fake-Klassifikator für Tests und E2E; Mistral-Anbieter über das Gateway (F06); Kontingente `guard_document`, `guard_question` (Migration) · Commit
- [x] **5. Pipeline-Schritt + Ausschluss** — `F07-AC1`, `F07-AC5`, `F07-AC7`, `F07-AC11` · Migration (Status `screening`, `screening_result`, `screened_pages`, Check-Constraint, `injection_findings`) + RLS-Tests; F02-Neuversuch angepasst; F03/F05 lesen `screened_pages`; Integrationstests · Commit `feat(api): screen documents before extraction`
- [x] **6. Begrenzer gemeinsam, Ausgabe prüfen, Fragen prüfen** — `F07-AC8`, `F07-AC9`, `F07-AC10` · Commit
- [x] **7. Oberfläche „Angriff erkannt“ + Musterdokumente zum Ausprobieren** — `F07-AC6`, `F07-AC14` · Vitest + Playwright (beide Musterdokumente) · Landkarte: „Sicherheitsrisiken von LLM-Anwendungen“ auf live · Commit `feat(web): show detected prompt injection`
- [ ] **8. Realtest** — beide Musterdokumente gegen echtes Mistral (OCR + Klassifikator) hochladen: Befunde und Ausschluss prüfen; ein normaler Arztbrief bleibt `clean`; Ergebnis notieren
- [x] **Protokoll-Ereignis `blocked` (`F07-AC11`)** — umgesetzt mit F12 Aufgabe 2 (Commit 972d6ae): je Befund und blockierter Frage ein Ereignis mit Schicht und Regel-ID.
- [x] **9. Eigene Prüfanweisung für Anfragen, ehrliche Meldung bei unbrauchbarer Prüfung** — `F07-AC15`, `F07-AC16` (ergänzt 02.11.2026 nach Realtest: Ministral blockierte „Plane eine Blutdruckkontrolle …“) · `REQUEST_PROMPT` in `app/security/classifier.py`, `classify_question` nutzt sie, Dokumente behalten ihre Anweisung; 503 `screening_unusable`; Protokoll `rule_id = classifier:<Kategorie aus fester Liste>` bzw. `error_code = classifier_unusable` · Tests rot → grün · Messung vorher/nachher mit `make request-report` (F13 Aufgabe 6)
