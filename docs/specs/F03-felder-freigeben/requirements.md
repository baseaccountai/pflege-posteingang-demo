# F03 – Felder vorschlagen & freigeben: Anforderungen

Status: freigegeben 25.10.2026 · Stufe: 1 · Bildschirm: 3 (Prüfen & Freigeben) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Aus dem OCR-Text schlägt ein LLM strukturierte Felder vor. **Ein Mensch prüft, korrigiert und gibt frei** – erst dann landen Daten in der Bewohnerakte. Der Medikationsabgleich (neu / abgesetzt / unverändert) wird deterministisch berechnet, nicht vom LLM. Grundlage: Design 2, 5.4, 5.5 (Medikationsabgleich), Review Focus „falscher Bewohner“, „schlechte Scans“.

## User Stories

- **US-1:** Als Pflegekraft möchte ich die erkannten Felder neben dem Original sehen und korrigieren, damit nur geprüfte Daten in die Akte kommen.
- **US-2:** Als Pflegekraft möchte ich bei einem neuen Medikationsplan sofort sehen, was neu, abgesetzt oder unverändert ist.
- **US-3:** Als Pflegekraft möchte ich den Bewohner ausdrücklich bestätigen, damit ein Dokument nicht beim falschen Bewohner landet.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F03-AC1 | WENN die OCR eines Dokuments lesbaren Text geliefert hat (F02), DANN soll das System per LLM einen Feldvorschlag nach festem JSON-Schema erzeugen: Dokumenttyp, Dokumentdatum, ausstellende Stelle, Bewohnername laut Dokument, Diagnosen[], Medikamente[] (Name, Stärke, Dosierung morgens/mittags/abends/nachts, Hinweis), Wiedervorlagen[] (Titel, Fälligkeit). |
| F03-AC2 | FALLS die LLM-Antwort nicht dem Schema entspricht, DANN soll das System einmal erneut anfragen und danach leere Felder mit dem Hinweis „Kein Vorschlag möglich – bitte manuell erfassen“ anzeigen, statt geratene Werte. |
| F03-AC3 | Das System soll für jeden vorgeschlagenen Wert eine wörtliche Fundstelle aus dem OCR-Text verlangen; FALLS die Fundstelle (nach Normalisierung von Leerzeichen und Groß-/Kleinschreibung) nicht im OCR-Text vorkommt, DANN soll das System den Wert als „nicht im Dokument gefunden“ markieren und nicht vorbelegen. |
| F03-AC4 | Die Prüfansicht soll Original (Bild/PDF) und Felder nebeneinander (Desktop/Tablet) bzw. umschaltbar (Handy) zeigen; jedes Feld ist bearbeitbar, Listeneinträge können hinzugefügt und entfernt werden. |
| F03-AC5 | Das System soll einen Bewohner nur aus den Bewohnern der eigenen Wohnbereiche vorschlagen (Namensabgleich) und die Auswahl als Pflichtfeld „Bewohner bestätigen“ anzeigen; ohne aktive Bestätigung ist „Freigeben“ deaktiviert. |
| F03-AC6 | WENN kein Bewohner sicher zugeordnet werden kann, DANN soll das System keinen vorauswählen und „Bewohner bitte auswählen“ anzeigen. |
| F03-AC6a | WENN die Pflegekraft den gewählten Bewohner ändert, DANN soll das System die Bestätigung zurücksetzen und den Medikationsabgleich für den neuen Bewohner neu berechnen. |
| F03-AC7 | WENN der Dokumenttyp `medikationsplan` ist und ein Bewohner gewählt ist, DANN soll das System jedes Medikament als **neu**, **geändert** (Dosierung/Stärke anders), **unverändert** oder **abgesetzt** (in der Akte aktiv, im neuen Plan fehlend) kennzeichnen. |
| F03-AC8 | WENN die Pflegekraft ein Dokument im Status `ready_for_review` freigibt, DANN soll das System in einer Transaktion unter Sperre des Bewohners den Medikationsabgleich neu berechnen, Diagnosen und Wiedervorlagen mit Herkunft speichern, Medikamente anlegen/ändern/absetzen und je Änderung ein `medication_events`-Ereignis (Art, Dokument, vorher/nachher, bestätigt von) schreiben und das Dokument auf `approved` setzen. |
| F03-AC8a | FALLS sich die Akte des Bewohners seit dem Anzeigen des Abgleichs geändert hat (anderes Abgleich-Ergebnis), DANN soll das System die Freigabe mit „Die Akte wurde inzwischen geändert – bitte Abgleich prüfen“ ablehnen und den neuen Abgleich anzeigen. |
| F03-AC9 | FALLS das Dokument nicht (mehr) im Status `ready_for_review` ist (bereits freigegeben, verworfen oder noch in Verarbeitung), DANN soll das System Freigabe und Verwerfen ablehnen („bereits freigegeben von …“ bzw. „bereits verworfen“) und nichts speichern; freigegebene und verworfene Dokumente sind unveränderlich. |
| F03-AC10 | Das System soll „Verwerfen“ anbieten; verworfene Dokumente erhalten Status `rejected` und erzeugen keine Akteneinträge. |
| F03-AC11 | WENN ein Dokument freigegeben wurde, DANN soll das System die Indizierung für Fragen (F05) anstoßen. |
| F03-AC12 | Das System soll in der Prüfansicht das genutzte Modell anzeigen und den Satz „KI-Vorschlag – bitte jedes Feld prüfen“. |
| F03-AC13 | WO `LLM_PROVIDER=ollama` gesetzt ist, soll das System Ollama mit demselben Schema nutzen, ohne Codeänderung. |

## Nicht im Umfang

Pseudonymisierung vor dem LLM (F06), Injection-Prüfung (F07), Bearbeiten bereits freigegebener Einträge.
