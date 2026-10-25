# F10 – Musterdaten, nächtlicher Reset, Hinweise: Anforderungen

Status: Entwurf · Stufe: 1 · Bildschirme: alle · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Die öffentliche Demo arbeitet nur mit erfundenen, sichtbar markierten Musterdaten, setzt sich jede Nacht zurück, schützt Budget und Verfügbarkeit und zeigt verständliche Hinweise, wenn etwas schläft oder ein Limit erreicht ist. Grundlage: Design 3 (Anti-Ziele), 4 (Budget), 5.6, 5.7, 10, 12; Review Focus „Schlaf/Limit“.

## User Stories

- **US-1:** Als Besucher möchte ich sofort mit realistischen Musterdaten arbeiten können, ohne etwas hochzuladen.
- **US-2:** Als Bewerber möchte ich sicher sein, dass Besucher-Uploads nicht dauerhaft gespeichert bleiben und die Kosten begrenzt sind.
- **US-3:** Als Besucher möchte ich verstehen, warum etwas gerade nicht geht.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F10-AC1 | Das System soll Musterdaten mit zwei Wohnbereichen (WB1, WB2) und je 3 erfundenen Bewohnern bereitstellen (z. B. „Hr. Muster-Bauer“, „Fr. Beispiel“), mit bereits freigegebenen Medikationen, Diagnosen, Wiedervorlagen und Chunks. |
| F10-AC2 | Das Repo soll unter `samples/` Musterdokumente als PDF und Bild mit Wasserzeichen „MUSTER“ enthalten: mindestens je ein Arztbrief, Medikationsplan und Überleitungsbogen sowie unter `samples/bad/` eine leere Seite, ein unscharfes Foto, ein schiefes Foto und ein Nicht-Pflegedokument. |
| F10-AC3 | Die Musterdokumente sollen per Skript (`samples/generate.py`) reproduzierbar erzeugt werden; kein Musterdokument enthält Namen realer Personen, Einrichtungen oder Praxen. |
| F10-AC4 | Das System soll auf jedem Bildschirm das gelbe Banner „MUSTERDATEN · keine echten Personen“ zeigen. *(umgesetzt in Phase 0, hier als Regressionstest)* |
| F10-AC5 | WENN der nächtliche Reset läuft (täglich 03:00 Uhr deutscher Zeit, GitHub Action), DANN soll das System alle Nutzerdaten und Uploads löschen, den Musterdatenstand wiederherstellen und die Passwörter der Demo-Konten zurücksetzen. |
| F10-AC6 | Der Reset soll ohne LLM- und OCR-Aufrufe auskommen (vorberechnete Chunks und Embeddings im Seed). |
| F10-AC7 | FALLS der Reset fehlschlägt, DANN soll die GitHub Action fehlschlagen (Benachrichtigung an den Bewerber) und den vorherigen Stand nicht halb gelöscht hinterlassen (Datenbank-Teil in einer Transaktion). |
| F10-AC8 | Das System soll einen Keep-alive-Lauf (GitHub Action, alle 2 Tage) ausführen, der API und Datenbank anfragt, damit Supabase nicht pausiert. |
| F10-AC9 | Das System soll eine globale Tagesobergrenze für OCR-Seiten (`DAILY_OCR_PAGE_LIMIT`, Start 100) und LLM-Aufrufe (`DAILY_LLM_CALL_LIMIT`, Start 300) erzwingen; Zählung serverseitig in der Datenbank, atomar. |
| F10-AC10 | WENN eine Obergrenze erreicht ist, DANN soll die API mit 429 antworten und die App „Tageskontingent der Demo erreicht – Musterdaten bleiben ansehbar, morgen geht es weiter.“ zeigen; lesende Funktionen (Akte, Liste, Posteingang) bleiben nutzbar. |
| F10-AC11 | WENN die API nicht antwortet, 502/503 liefert oder länger als 5 Sekunden braucht, DANN soll die App „Demo startet gerade … (bis zu 30 Sekunden)“ mit automatischem Neuversuch zeigen statt einer leeren Seite oder eines Fehlers. |
| F10-AC12 | Das System soll im Footer bzw. auf `/projekt` den Hinweis zeigen, dass Daten jede Nacht zurückgesetzt werden. |

## Nicht im Umfang

Sandbox pro Besucher (bewusst nicht, Design 12), Kostenmessung in Euro (Zählung als Näherung, Kostenschätzung in ADR 0003).
