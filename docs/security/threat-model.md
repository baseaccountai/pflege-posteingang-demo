# Bedrohungsmodell

Stand: 01.11.2026 · Orientierung: **OWASP Top 10 für LLM-Anwendungen (2025)** · lokaler Betrieb komplett (Phase 8: Keycloak, Docling, Ollama); Zeilen mit „offen“ sind noch nicht umgesetzt.

## Schutzgüter

| Schutzgut | Warum schützenswert |
|---|---|
| Gesundheitsdaten der (Muster-)Bewohner | besondere Kategorie nach Art. 9 DSGVO |
| Trennung der Wohnbereiche | Pflegekräfte dürfen nur eigene Bewohner sehen |
| Integrität der Akte (v. a. Medikation) | falsche Dosis gefährdet Bewohner |
| Kosten / Verfügbarkeit | Budget, öffentliche Demo |

## Vertrauensgrenzen

| Grenze | Beschreibung |
|---|---|
| Browser ↔ BFF | nur Session-Cookie, keine Tokens im Browser |
| BFF ↔ API | Access-Token; API prüft Signatur (JWKS), `iss`, `aud`, `exp`, Algorithmen |
| API ↔ Supabase | Zugriff im Namen von Nutzer/Agent, RLS erzwingt Wohnbereich |
| API ↔ Cloud-LLM | nur pseudonymisierte Texte – gilt auch für den Injection-Klassifikator; die Prüfung davor (Regeln, versteckter Text) läuft lokal im Backend |
| API ↔ Cloud-OCR | **sieht Rohdaten** (bekannte Grenze; lokal: Docling) |
| lokaler Modus (`make up-local`) | kein Dienst außerhalb des Rechners: Docling liest das Original lokal, alle Modellrollen laufen über Ollama, auch wenn ein `MISTRAL_API_KEY` gesetzt wäre (`apps/api/tests/providers/test_local_mode.py`); `.env` wird nicht gelesen. Agenten-Token lokal selbst signiert (Keycloak stellt kein `act` aus, ADR 0012); ein lokaler Auftrag darf länger dauern als das Token gilt (bewusst, ADR 0012 „Abweichung lokal“). Keycloak und Docling lauschen nur auf 127.0.0.1, das Keycloak-Admin-Passwort ist zufällig (`infra/.local/`, nicht im Repo) |
| Dokumentinhalt ↔ Prompt | Dokumente sind **Daten**, keine Anweisungen |

## OWASP Top 10 für LLM-Anwendungen – Zuordnung

| Risiko | Relevanz in der Demo | Maßnahme | Feature | Status |
|---|---|---|---|---|
| LLM01 Prompt Injection (direkt/indirekt) | hoch – präparierte Dokumente | fünf Schichten (Design 5.5a) | F07, F13 | umgesetzt für Dokumente, Fragen und Agenten-Aufträge (Agent: siehe LLM06); gemessen: Regeln allein 12,7 % Erkennung bei 0 % Fehlalarm (CI-Schwelle `apps/api/tests/security/thresholds.json`), Prüfmodell 88,8 %, beide Schichten 89,6 % bei 11,3 % Fehlalarm (Bericht `docs/security/reports/2026-10-31-injection.md`, `ministral-8b-latest`); Tests `apps/api/tests/security/` (Korpus, Szenarien mit den präparierten PDFs, Agent liest einen Brief mit Anweisung an die KI) |
| LLM02 Sensitive Information Disclosure | hoch | Pseudonymisierung, Ausgabeprüfung, RLS | F06, F08 | umgesetzt für Fragen, Feldvorschlag und Agent (F06, F08): kein Klarname an ein Modell, auch nicht in den Werkzeugergebnissen des Agenten (`tests/security/test_scenarios.py`, `tests/privacy/`, `tests/rls/test_agent_runner.py`); feste Prompts enthalten keinen Nachnamen der Musterdaten (`tests/privacy/test_fixed_prompts.py`); RLS je Wohnbereich (`tests/rls/`) |
| LLM03 Supply Chain | mittel | gepinnte Abhängigkeiten, Lockfiles, CI | F11 | offen |
| LLM04 Data and Model Poisoning | mittel – Uploads | menschliche Freigabe vor Indizierung | F03, F07 | offen |
| LLM05 Improper Output Handling | mittel | Ausgabe prüfen, nur erlaubte Quellen | F05, F07 | umgesetzt: Antworten nur mit geprüften Quellenzitaten, keine Links/Bilder in der Ausgabe (`apps/api/tests/security/test_output.py`, `tests/rls/test_questions.py`) |
| LLM06 Excessive Agency | hoch – Agent | eingeschränktes Agenten-Token, Bestätigungspflicht, keine gefährlichen Werkzeuge | F08 | umgesetzt: eigenes Agenten-Token (`act`-Claim, RFC 8693 Token Exchange; höchstens 5 Minuten gültig), Datenbankrechte: lesen im eigenen Wohnbereich, schreiben nur Vorschläge und die Wiedervorlage eines bestätigten Vorschlags, keine Originale, Befunde, Protokolle (`tests/rls/test_agent_rls.py`), fünf Werkzeuge ohne Löschen oder Ändern (`tests/rls/test_agent_tools.py`), schreibt nur offene Vorschläge, die die Pflegekraft bestätigt (`tests/rls/test_agent_proposals_route.py`), höchstens 4 Werkzeugschritte, 5 Modellaufrufe, 60 Sekunden; anderer Wohnbereich = „nichts gefunden“ ohne Modellaufruf; Szenarien `tests/security/test_scenarios.py`. Realtest mit Zitadel und Mistral steht noch aus |
| LLM07 System Prompt Leakage | niedrig | keine Geheimnisse im System-Prompt | F05 | offen |
| LLM08 Vector and Embedding Weaknesses | hoch – RAG | RLS auf Chunks, Metadaten-Filter | F05 | offen |
| LLM09 Misinformation | mittel | Quellen in jeder Antwort, Mensch prüft | F03, F05 | offen |
| LLM10 Unbounded Consumption | mittel – Kosten | Upload-Limit, Tagesobergrenze | F10 | offen |

## Offene Grenzen (ehrlich benannt)

- Cloud-OCR sieht Rohdaten; nur der lokale Modus vermeidet das.
- Kein Filter erkennt Prompt-Injection zuverlässig; Ziel ist begrenzte Wirkung, nicht perfekte Erkennung.
- Protokoll (F12): Akteur und Wohnbereich setzt die Datenbank aus den Claims, Zusatzangaben
  sind nur Kennungen. Das Backend kann aber falsche, eigene Modell-Ereignisse schreiben, und
  der Modellname ist freier Text aus seiner Konfiguration – das Protokoll vertraut dem Backend
  so weit, wie es die Datenbank ohnehin tut.
- Protokoll (F12-AC8): Fällt die Datenbank beim Schreiben eines Ereignisses aus, wird ein
  Ergebnis nicht ausgeliefert; eine Blockierung bleibt bestehen, ihr Ereignis kann dann aber
  fehlen (bewusste Entscheidung: Sperren vor Vollständigkeit des Protokolls).
