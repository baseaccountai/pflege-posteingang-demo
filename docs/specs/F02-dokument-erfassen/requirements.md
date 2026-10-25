# F02 – Dokument erfassen (Kamera/Upload, OCR): Anforderungen

Status: Entwurf · Stufe: 1 · Bildschirm: 2 (Posteingang) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Pflegekräfte fotografieren oder laden ein Papierdokument hoch; das System liest es per OCR (öffentlich Mistral OCR, lokal Docling) als Markdown ein. Grundlage: Design 2, 5.4, 6.

## User Stories

- **US-1:** Als Pflegekraft möchte ich einen Arztbrief direkt mit der Handykamera erfassen, damit ich nichts abtippen muss.
- **US-2:** Als Pflegekraft möchte ich im Posteingang sehen, welche Dokumente warten, freigegeben oder fehlerhaft sind.
- **US-3:** Als Betreiber der Demo möchte ich Kosten und Missbrauch begrenzen.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F02-AC1 | Das System soll im Posteingang „Foto aufnehmen“ (Kamera, Rückseite) und „Datei hochladen“ anbieten; erlaubt sind JPEG, PNG und PDF bis 10 MB und höchstens 5 Seiten. |
| F02-AC2 | Das System soll über dem Upload dauerhaft den Hinweis „Bitte keine echten Personendaten hochladen.“ anzeigen. |
| F02-AC3 | FALLS eine Datei einen anderen Typ (geprüft am Inhalt, nicht nur an der Endung), mehr als 10 MB oder mehr als 5 Seiten hat, DANN soll das System sie ohne OCR-Aufruf ablehnen und den Grund verständlich anzeigen. |
| F02-AC4 | WENN eine gültige Datei hochgeladen wird, DANN soll das System sie im privaten Speicher unter dem Wohnbereich der Pflegekraft ablegen, ein Dokument mit Status `uploaded` anlegen und sofort im Posteingang anzeigen. |
| F02-AC5 | WENN ein Dokument angelegt wurde, DANN soll das System im Hintergrund die OCR ausführen, das Markdown speichern und den Feldvorschlag (F03-AC1) erzeugen; der Status wechselt von `processing` erst nach beiden Schritten auf `ready_for_review`. Der Posteingang aktualisiert den Status ohne Neuladen. |
| F02-AC6 | FALLS die OCR keinen oder kaum Text liefert (leere Seite, unscharf, < 80 Zeichen) oder der Text kein Pflegedokument erkennen lässt, DANN soll das System den Status `unreadable` setzen und „Dokument nicht lesbar – bitte neu fotografieren (gerade, hell, ganze Seite)“ anzeigen, ohne Felder vorzuschlagen. |
| F02-AC7 | FALLS der OCR-Dienst nicht erreichbar ist oder einen Fehler liefert, DANN soll das System den Status `failed` setzen, „Texterkennung gerade nicht verfügbar“ anzeigen und „Erneut versuchen“ anbieten. |
| F02-AC8 | Das System soll pro Login-Sitzung höchstens 5 Uploads zulassen (Zähler an der serverseitig erzeugten Sitzungs-ID, nicht am Demo-Konto, da Besucher die Konten teilen); danach „Upload-Limit erreicht – Musterdokumente bleiben nutzbar“. Die globale Tagesobergrenze regelt F10. |
| F02-AC9 | WO `OCR_PROVIDER=docling` gesetzt ist, soll das System Docling statt Mistral OCR nutzen, ohne Codeänderung. |
| F02-AC10 | Das System soll eine PDL beim Upload den Wohnbereich wählen lassen; Pflegekräfte laden immer in ihren eigenen Wohnbereich. |
| F02-AC11 | Der Posteingang soll nur Dokumente der eigenen Wohnbereiche zeigen, mit Typ (falls erkannt), Uhrzeit, Status-Badge (wartet, in Bearbeitung, freigegeben, nicht lesbar, Fehler) und Link zur Prüfung (F03). |

## Nicht im Umfang

Injection-Prüfung (F07, Status `suspicious`), Pseudonymisierung (F06), mehrseitige Bildserien (ein Foto = eine Seite).
