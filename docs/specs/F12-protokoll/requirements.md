# F12 – Protokoll für die Pflegedienstleitung: Anforderungen

Status: Entwurf 28.10.2026 · Stufe: 2 · Bildschirm: Protokoll (neu, nur PDL) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Die Pflegedienstleitung sieht, wer wann was mit KI gemacht hat – Mensch oder Agent, mit welchem Modell, und was blockiert wurde (Design 5.6). Das Protokoll ist nachträglich nicht änderbar und enthält keine Dokument- oder Frageinhalte. Rundgang Minute 5.

## User Stories

- **US-1:** Als PDL möchte ich nachvollziehen, welche KI-Schritte in meiner Einrichtung liefen und welche Angriffe abgewehrt wurden.
- **US-2:** Als Prüfer der Bewerbung möchte ich sehen, dass Mensch und Agent im Protokoll unterscheidbar sind.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F12-AC1 | Das System soll für diese Aktionen je ein Ereignis schreiben: Upload, OCR, Prüfung (F07), Feldvorschlag, Freigabe, Ablehnung, Frage, Agent-Auftrag, Agent-Werkzeug, Agent-Vorschlag, Bestätigung, Verwerfen, Blockierung (F06-AC10, F07-AC11, F08-AC9), Kontingent erschöpft. |
| F12-AC2 | Jedes Ereignis soll enthalten: Zeitpunkt, Aktion, Ergebnis (`ok` \| `blocked` \| `error`), Akteur-Art (`human` \| `agent`), Akteur (Anzeigename), bei Agent zusätzlich „im Auftrag von <Anzeigename>“, Wohnbereich, Modell (falls eines beteiligt war), Dokument- bzw. Bewohner-ID (falls vorhanden) und Detail-Kennungen (Regel-ID, Werkzeugname, Fehlercode). |
| F12-AC3 | Das System soll im Protokoll keine Dokumenttexte, Fragetexte, Antworten, Namen von Bewohnern, Pseudonym-Zuordnungen oder Tokens speichern. |
| F12-AC4 | Akteur, Akteur-Art und Wohnbereich sollen aus den Claims der Datenbanksitzung stammen (nicht aus Parametern der Anfrage); ein Ereignis kann nicht im Namen eines anderen geschrieben werden. Ereignisse zu Zustandsänderungen (Upload, Statuswechsel des Dokuments, Freigabe, Ablehnung, Vorschlag, Bestätigung, Verwerfen, Wiedervorlage des Agenten) sollen Datenbank-Trigger an den Fachtabellen schreiben; das Backend kann sie nicht selbst erzeugen. |
| F12-AC5 | Das System soll Ereignisse nur einfügen lassen; Ändern und Löschen ist für alle Rollen außer dem nächtlichen Reset (F10) unmöglich. |
| F12-AC6 | Nur die PDL soll das Protokoll lesen können (RLS); Pflegekräfte bekommen unter `/protokoll` den Bildschirm „Kein Zugriff“, und die Navigation zeigt den Eintrag nur der PDL. |
| F12-AC7 | Die Seite `/protokoll` soll die Ereignisse absteigend nach ihrer fortlaufenden Nummer zeigen (50 je Seite, „Ältere laden“ über die kleinste angezeigte Nummer), mit Filtern „nur Agent“ und „nur blockiert“; Agent-Ereignisse sind optisch gekennzeichnet. |
| F12-AC8 | Ereignisse zu Zustandsänderungen sollen in derselben Transaktion wie die Änderung entstehen (Trigger, AC4) – ohne Ereignis keine Änderung. Ereignisse zu Modellaufrufen, Fragen, Werkzeugen und Blockierungen (Backend über `app.log_event`) sollen nach dem Aufruf in einer eigenen Transaktion geschrieben werden; FALLS das fehlschlägt, DANN bleibt eine Blockierung trotzdem bestehen und die Antwort wird nicht ausgeliefert. |
| F12-AC9 | `app.log_event` soll nur die Aktionen `ocr`, `screening`, `extraction`, `question`, `agent_task`, `agent_tool`, `blocked`, `quota_exhausted` annehmen; Zustandsänderungs-Aktionen werden abgelehnt. |

## Nicht im Umfang

- Export, Aufbewahrungsfristen, Auswertungen/Diagramme.
- Protokoll von Logins/Logouts (liegt beim Identity Provider).
