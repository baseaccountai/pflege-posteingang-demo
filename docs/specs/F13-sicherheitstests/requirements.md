# F13 – Automatische Sicherheitstests mit Bericht: Anforderungen

Status: freigegeben 29.10.2026 (im Chat) · Stufe: 2 · Bildschirme: – (Bericht verlinkt von Landkarte und `/projekt`)

## Einführung

Die Schutzschichten aus F06–F08 werden **gemessen**, nicht nur behauptet: ein Testkorpus mit Angriffen und harmlosen Pflegetexten läuft in jeder CI kostenlos gegen die Regeln; ein Lauf gegen das echte Modell erzeugt einen Bericht mit Erkennungs- und Fehlalarmrate (Design 5.5a „Methodik“). Rundgang Minute 5.

## User Stories

- **US-1:** Als Prüfer der Bewerbung möchte ich eine Zahl sehen: Wie viele Angriffe erkennt der Schutz, wie oft schlägt er bei harmlosen Texten falsch an?
- **US-2:** Als Entwickler möchte ich, dass eine Änderung an den Mustern, die die Erkennung verschlechtert, die CI rot macht.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F13-AC1 | Der Testkorpus (`apps/api/tests/security/corpus/`) soll mindestens 120 Angriffe und 60 harmlose Pflegetexte enthalten, je Eintrag: ID, Text, Sprache, Kategorie (`role_override`, `ignore_instructions`, `exfiltration`, `dose_manipulation`, `tool_abuse`, `hidden_instruction`, `jailbreak`, `benign`), Quelle und Lizenz. |
| F13-AC2 | Der Korpus soll Einträge aus mindestens drei Quellen enthalten: öffentlicher Datensatz mit deutschen Beispielen (deepset/prompt-injections, Apache-2.0), angelehnt an BIPIA/Greshake et al. (indirekte Injection in Dokumenten) und eigene Pflege-Angriffe (Datenabfluss, Dosis-Manipulation, Agenten-Missbrauch, versteckte Schrift). |
| F13-AC2a | Die Kennzahlen sollen so definiert sein: Ein Eintrag gilt als **erkannt**, wenn mindestens eine geprüfte Schicht ihn markiert. **Erkennungsrate** = erkannte Angriffe ÷ alle Angriffe; **Fehlalarmrate** = erkannte harmlose Texte ÷ alle harmlosen Texte; beide gesamt und je Kategorie (jeder Eintrag hat genau eine Kategorie) und je Schicht (Schicht 1 allein, Schicht 2 allein, kombiniert). Versteckte Schrift wird nicht im Textkorpus gemessen, sondern in den Szenario-Tests (AC4). |
| F13-AC3 | WENN die CI läuft, DANN soll sie den Korpus gegen Schicht 1 (Regeln) prüfen und fehlschlagen, FALLS die Erkennungsrate unter den in `apps/api/tests/security/thresholds.json` festgehaltenen Wert fällt oder die Fehlalarmrate darüber steigt – ohne Modellaufruf. |
| F13-AC4 | Die CI soll Szenario-Tests ausführen: präparierte Musterdokumente (F07-AC12) → Befunde; Agent mit Dokument-Anweisung → kein Schreiben ohne Bestätigung (F08-AC13); Agent fragt WB2 → leer (F08-AC10); kein Klarname in ausgehenden Modellaufrufen (F06). |
| F13-AC5 | `make security-report` soll den Korpus gegen Schicht 1 + 2 mit dem echten Klassifikator laufen lassen (Bewerber, eigenes Terminal; liest nur `MISTRAL_API_KEY` aus `.env`) und `docs/security/reports/<Datum>-injection.md` schreiben: Erkennungsrate und Fehlalarmrate je Schicht und je Kategorie, Beispiele für Fehler, Modell, Datum, Anzahl Aufrufe. |
| F13-AC6 | Der Bericht soll Grenzen offen benennen (Korpusgröße, Sprachmix, Klassifikator nur ein Modell, keine adaptiven Angreifer). |
| F13-AC7 | Landkarte (Eintrag „Sicherheitsrisiken von LLM-Anwendungen“) und `/projekt` sollen den Bericht verlinken, den die Konstante `SECURITY_REPORT` in `content/requirements-map.ts` nennt; der Bericht-Commit setzt sie, ein Test prüft, dass die Datei existiert. Ohne Bericht zeigt der Eintrag „Bericht folgt“. |
| F13-AC8 | Das Bedrohungsmodell (`docs/security/threat-model.md`) soll für LLM01, LLM02, LLM05, LLM06 den Status und den Verweis auf Tests und Bericht nennen. |

## Nicht im Umfang

- garak oder promptfoo in der CI (Kosten, Laufzeit) – optional als zusätzlicher manueller Lauf, falls Zeit bleibt.
- Adaptive Angriffe (automatisch nachgeschärfte Prompts).
