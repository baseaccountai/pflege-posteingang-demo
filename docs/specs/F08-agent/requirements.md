# F08 – Agenten-Rechte + bestätigte Aktionen: Anforderungen

Status: freigegeben 29.10.2026 (im Chat) · Stufe: 2 · Bildschirme: 4 (Fragen), 7 (Bewohnerakte), 8 (Kein Zugriff) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Der Agent ist das Chat-Modell mit Werkzeugen, ausgeführt im Backend (Design 5.5). Er handelt **im Auftrag** der angemeldeten Pflegekraft mit einem **eigenen, kurzlebigen, eingeschränkten Token** aus OAuth 2.0 Token Exchange (RFC 8693, `act`-Claim). Er kann lesen und Wiedervorlagen **vorschlagen**; gespeichert wird erst nach Bestätigung durch den Menschen. Gefährliche Werkzeuge gibt es nicht, fremde Wohnbereiche sperrt die Datenbank (Rundgang Minuten 3 und 4).

## User Stories

- **US-1:** Als Pflegekraft möchte ich den Agenten bitten, einen neuen Medikationsplan mit der Akte abzugleichen und mich an eine Kontrolle zu erinnern.
- **US-2:** Als Pflegekraft möchte ich jede schreibende Aktion des Agenten vorher sehen und bestätigen.
- **US-3:** Als Prüfer der Bewerbung möchte ich sehen, dass der Agent nicht mehr darf als der Mensch – auch wenn man ihn darum bittet oder ein Dokument es ihm befiehlt.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F08-AC1 | WENN ein Agent-Auftrag beginnt, DANN soll das Backend das Access-Token des Nutzers per Token Exchange (RFC 8693) beim Identity Provider gegen ein Agenten-Token tauschen: Subjekt = Nutzer, `act`-Claim = Agenten-Identität. Das Backend nimmt das Agenten-Token höchstens 5 Minuten nach seiner Ausstellung (`iat`) an, hält es nur im Speicher und verwirft es nach dem Auftrag – auch wenn der Identity Provider es länger ausstellt (Spike 31.10.2026: Zitadel 1 h, ADR 0012). |
| F08-AC2 | WO der Identity Provider kein Token Exchange anbietet (`AGENT_TOKEN_MODE=self_signed`), soll das Backend nach Prüfung des Nutzer-Tokens selbst ein signiertes Agenten-JWT mit denselben Claims ausstellen (eigener Schlüssel mit `kid`, eigener Aussteller, Gültigkeit höchstens 5 Minuten); die Prüfung im Backend behandelt beide Wege gleich, und `/projekt` nennt den aktiven Weg offen (Rückfall: „die API stellt das Agenten-Token selbst aus“). |
| F08-AC2a | Bevor Werkzeuge und RLS-Regeln für den Agenten gebaut werden, soll ein Spike festhalten (ADR 0012), welchen Weg die öffentliche Demo nutzt, mit den tatsächlich ausgestellten Claims (`iss`, `aud`, `sub`, `act`, `exp − iat`, Rollen-Claim); die Prüfung (AC3) wird gegen genau diese Claims getestet. |
| F08-AC3 | Das Backend soll ein Agenten-Token nur annehmen, wenn Signatur, Aussteller, Zielgruppe, Ablauf, Subjekt (= Nutzer der Sitzung) und `act.sub` (= konfigurierte Agenten-Identität) stimmen; daraus entsteht ein Principal mit `actor_type = agent` und den Wohnbereichen des Nutzers. Das Agenten-Token gelangt nie in den Browser. |
| F08-AC4 | Der Agent soll genau diese Werkzeuge haben: `dokumente_durchsuchen` (F05-Suche), `bewohnerakte_lesen`, `medikation_abgleichen` (Dokument vs. aktuelle Akte: neu / abgesetzt / geändert / unverändert), `wiedervorlagen_auflisten`, `wiedervorlage_vorschlagen`. Jedes Werkzeug läuft mit dem Agenten-Principal (RLS). |
| F08-AC5 | WENN der Agent `wiedervorlage_vorschlagen` nutzt, DANN soll das System nur einen **Vorschlag** speichern (Bewohner, Titel, Fälligkeit; gültig 15 Minuten) und in der Oberfläche „Bestätigen“ / „Verwerfen“ anbieten; nichts wird in die Akte geschrieben. |
| F08-AC6 | WENN die Pflegekraft einen Vorschlag bestätigt, DANN soll das System zuerst **als Mensch** den Vorschlag auf `confirmed` setzen und danach die Wiedervorlage als Agent mit `confirmed_by` = Pflegekraft anlegen; die Akte zeigt „vom Agenten angelegt · bestätigt von <Rolle>“ (F04-AC6). Ein Vorschlag lässt sich nur einmal, nur von der Person, für die er erstellt wurde, und nur vor Ablauf bestätigen. |
| F08-AC7 | Die Datenbank soll für `actor_type = agent` nur Lesen auf Bewohner, Dokumente, Chunks, Medikation, Diagnosen, Wiedervorlagen erlauben und Schreiben nur als Einfügen in `agent_proposals` (Status `open`) sowie in `follow_ups` **zu einem Vorschlag, den ein Mensch bereits auf `confirmed` gesetzt hat** (höchstens eine Wiedervorlage je Vorschlag) – kein Ändern oder Löschen, keine Statusänderung an Vorschlägen, keine Medikation, keine Diagnosen, keine Freigaben (RLS, nicht nur Prompt). |
| F08-AC8 | WENN der Auftrag eine nicht vorhandene Fähigkeit verlangt (Medikation ändern, Daten löschen, Nachricht nach außen senden, anderen Wohnbereich lesen), DANN soll der Agent ablehnen und eine erlaubte Alternative anbieten (z. B. Wiedervorlage „Dosis mit Hausarzt klären“). |
| F08-AC9 | FALLS das Modell ein unbekanntes Werkzeug oder unzulässige Argumente aufruft, DANN soll das System den Aufruf nicht ausführen, ein Ereignis `blocked` (F12) schreiben und dem Modell „nicht erlaubt“ zurückgeben. |
| F08-AC10 | WENN der Agent nach Daten eines fremden Wohnbereichs sucht, DANN soll das Ergebnis leer sein wie bei einem nicht existierenden Bewohner (F05-AC7), und die Antwort soll zeigen „Dazu gibt es in deinem Wohnbereich nichts – der Agent hat dieselben Rechte wie du.“ |
| F08-AC11 | Die Oberfläche soll unter jeder Agent-Antwort die genutzten Werkzeuge zeigen („Agent nutzte: Medikationsabgleich, Wiedervorlage vorschlagen“) und eine sichtbare Liste „Das kann der Agent nicht“ (Medikation ändern, löschen, Nachrichten senden, andere Wohnbereiche). |
| F08-AC12 | Ein Agent-Auftrag soll höchstens 4 Werkzeugschritte, 5 Modellaufrufe und 60 Sekunden Gesamtzeit umfassen (*01.11.2026, Entscheidung Bewerber: nur im lokalen Modus per `AGENT_MAX_SECONDS` länger, `make up-local` setzt 600 s – `qwen3:8b` schreibt auf dem CPU-Laptop ~1,3 Tokens/s*) (danach Abbruch mit Hinweis), synchron in der Anfrage (keine Hintergrundaufgabe); jeder Modellaufruf zählt gegen `llm_call` (F10); Aufträge laufen durch Pseudonymisierung (F06) und Injection-Prüfung (F07-AC9). |
| F08-AC13 | Werkzeugergebnisse mit Dokumentinhalt sollen dem Modell nur als markierte Daten übergeben werden (F07-AC8); eine Anweisung in einem Dokument kann keinen Werkzeugaufruf mit Schreibwirkung auslösen, ohne dass ein Mensch bestätigt. |

## Nicht im Umfang

- „Kann“-Werkzeuge aus Design 5.5: Übergabenotiz entwerfen, Rückfrage an Hausarzt entwerfen.
- Token Exchange mit Keycloak (lokal, Phase 8).
- Agent ohne angemeldeten Nutzer (Hintergrundjobs).
