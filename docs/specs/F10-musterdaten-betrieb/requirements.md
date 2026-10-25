# F10 – Musterdaten, nächtlicher Reset, Hinweise: Anforderungen

Status: Entwurf (überarbeitet nach Codex-Review) · Stufe: 1 · Bildschirme: alle · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Die öffentliche Demo arbeitet nur mit erfundenen, sichtbar markierten Musterdaten, setzt sich jede Nacht zurück, begrenzt Kosten und zeigt verständliche Hinweise, wenn etwas schläft oder ein Limit erreicht ist. Grundlage: Design 3 (Anti-Ziele), 4 (Budget), 5.6, 5.7, 10, 12; Review Focus „Schlaf/Limit“.

## User Stories

- **US-1:** Als Besucher möchte ich sofort mit realistischen Musterdaten arbeiten können, ohne etwas hochzuladen.
- **US-2:** Als Bewerber möchte ich sicher sein, dass Besucher-Uploads nicht dauerhaft gespeichert bleiben und die Kosten begrenzt sind.
- **US-3:** Als Besucher möchte ich verstehen, warum etwas gerade nicht geht, und trotzdem etwas sehen.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F10-AC1 | Das System soll Musterdaten mit zwei Wohnbereichen (WB1, WB2) und je 3 erfundenen Bewohnern bereitstellen, mit bereits freigegebenen Medikationen (inkl. Ereignisfolge), Diagnosen, Wiedervorlagen und durchsuchbaren Chunks. |
| F10-AC2 | Das Repo soll unter `samples/` Musterdokumente als PDF und Bild mit Wasserzeichen „MUSTER“ enthalten: mindestens je ein Arztbrief, Medikationsplan und Überleitungsbogen sowie unter `samples/bad/` eine leere Seite, ein unscharfes Foto, ein schiefes Foto und ein Nicht-Pflegedokument. |
| F10-AC3 | Die Musterdokumente sollen per Skript (`samples/generate.py`) reproduzierbar erzeugt werden; Personen-, Praxis- und Einrichtungsnamen stammen nur aus einer festen Liste erfundener Namen im Skript. |
| F10-AC4 | Das System soll auf jeder eigenen Seite (Start, Posteingang, Prüfansicht, Bewohnerliste, Akte, Fragen, Kein Zugriff, Fehlerseiten, Offline-Seite, Musterakte, `/projekt`) das Banner „MUSTERDATEN · keine echten Personen“ und den Footer „Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt“ zeigen; die Login-Seiten des Identity Providers sind ausgenommen. |
| F10-AC5 | WENN der nächtliche Reset läuft (03:00 Uhr deutscher Zeit ganzjährig, zulässige Verzögerung des Schedulers bis 30 min), DANN soll das System alle Besucherdaten (Dokumente, Dateien, Akteneinträge, Chunks, Sitzungen) löschen und den Musterdatenstand wiederherstellen. |
| F10-AC6 | Der Reset soll ohne LLM- und OCR-Aufrufe auskommen (vorberechnete Chunks und Embeddings im Seed) und die Kontingentzähler des laufenden Tages nicht zurücksetzen. |
| F10-AC7 | WÄHREND der Reset läuft, soll die API schreibende Anfragen mit „Demo wird gerade zurückgesetzt – bitte in einer Minute erneut versuchen“ (503) ablehnen und laufende Hintergrundverarbeitung keine Daten mehr schreiben. |
| F10-AC8 | FALLS der Reset fehlschlägt, DANN soll der Datenbankteil vollständig zurückgerollt werden, der Wartungsmodus enden und die GitHub Action fehlschlagen (Benachrichtigung an den Bewerber); ein erneuter Lauf ist gefahrlos wiederholbar. |
| F10-AC9 | Das System soll einen Keep-alive-Lauf (GitHub Action, alle 2 Tage) ausführen, der API und Datenbank anfragt, damit Supabase nicht pausiert. |
| F10-AC10 | Das System soll Tagesobergrenzen erzwingen für OCR-Seiten, LLM-Aufrufe (jeder Versuch inkl. Wiederholungen) und Embedding-Chunks; die Grenzen stehen serverseitig in der Datenbank, die Zählung ist atomar und nur mit positiven Mengen möglich. |
| F10-AC11 | Das System soll Eingabe- und Ausgabelänge jedes LLM-Aufrufs begrenzen, sodass die Tagesobergrenzen bei den in ADR 0003 festgehaltenen Preisen höchstens 0,50 € pro Tag ergeben. |
| F10-AC12 | WENN eine Obergrenze erreicht ist, DANN soll die API mit 429 antworten und die App „Tageskontingent der Demo erreicht – Musterdaten bleiben ansehbar, morgen geht es weiter.“ zeigen; lesende Funktionen (Akte, Liste, Posteingang) bleiben nutzbar. |
| F10-AC13 | WENN die API nicht antwortet, 502/503 liefert oder länger als 5 Sekunden braucht, DANN soll die App „Demo startet gerade … (bis zu 30 Sekunden)“ mit automatischem Neuversuch und einem Link „Musterakte ansehen“ zeigen statt einer leeren Seite. |
| F10-AC14 | Das System soll unter `/muster` eine öffentliche, statische Musterakte (ein Bewohner mit Medikation, Herkunft und Musterdokument) ohne Anmeldung und ohne API anzeigen; sie stammt aus einer im Repo erzeugten Datei aus dem Seed, nie aus zuvor geladenen Nutzerdaten. |
| F10-AC15 | Das System soll im Footer bzw. auf `/projekt` den Hinweis zeigen, dass Daten jede Nacht zurückgesetzt werden. |

## Nicht im Umfang

Sandbox pro Besucher (bewusst nicht, Design 12), Kostenmessung in Euro über die Mistral-Abrechnung (Zählung + Längenbegrenzung als konservative Näherung).
