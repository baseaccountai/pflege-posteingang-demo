# F08 – Agenten-Rechte + bestätigte Aktionen: Aufgaben

Jede Aufgabe: Test → Fehlschlag zeigen → Code → grün → Commit.

- [ ] **1. Spike Token Exchange in Zitadel** — `F08-AC1` · Bewerber schaltet die Beta-Funktion ein und legt den Service-User an (geführt); Skript tauscht ein Nutzer-Token und zeigt die Claims (`sub`, `act`, `exp`) · Ergebnis in ADR 0012 „Agenten-Token“ (Weg a oder Rückfall b, echte Claims) — `F08-AC2a`; **Tor:** Aufgaben 2–7 erst danach
- [ ] **2. Agenten-Token: Ausstellen und Prüfen** — `F08-AC1`, `F08-AC2`, `F08-AC3` · Unit-Tests beider Modi, Ablehnungsfälle · Commit `feat(api): issue and verify agent tokens`
- [ ] **3. RLS für den Agenten** — `F08-AC7` · Migration `agent_proposals` + Policies; DB-Tests (alle verbotenen Schreibwege, WB2 leer) · Commit `feat(db): restrict the agent in row level security`
- [ ] **4. Werkzeuge** — `F08-AC4`, `F08-AC10` · Tests je Werkzeug mit Agenten-Principal · Commit
- [ ] **5. Schleife mit Function Calling** — `F08-AC8`, `F08-AC9`, `F08-AC12`, `F08-AC13` · `chat_with_tools` für Fake/Mistral/Ollama; Skript-Tests (Ablehnung, unbekanntes Werkzeug, Grenzen, Dokument-Anweisung) · Commit `feat(api): run the agent with tools`
- [ ] **6. Vorschläge bestätigen/verwerfen** — `F08-AC5`, `F08-AC6` · Integrations- und DB-Tests · Commit
- [ ] **7. Oberfläche** — `F08-AC5`, `F08-AC10`, `F08-AC11` · BFF-Route, Umschalter „Fragen / Agent“, Vorschlagskarte; Vitest + Playwright · Landkarte: „RAG, agentenbasierte KI“ ohne Stufe-2-Teil · Commit `feat(web): add the agent with confirmed actions`
- [ ] **8. Realtest** — Rundgang Minuten 3 und 4 gegen echtes Mistral und Zitadel; Ergebnis notieren
