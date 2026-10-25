# F02 – Dokument erfassen (Kamera/Upload, OCR): Anforderungen

Status: freigegeben 25.10.2026 · Stufe: 1 · Bildschirm: 2 (Posteingang) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Pflegekräfte fotografieren oder laden ein Papierdokument hoch; das System liest es per OCR (öffentlich Mistral OCR, lokal Docling) als Markdown ein und erzeugt danach den Feldvorschlag (F03). Originaldateien liegen in einer Postgres-Tabelle mit Wohnbereichs-RLS (Entscheidung 25.10.2026, ADR folgt). Grundlage: Design 2, 5.4, 6; Review Focus „schlechte Scans“.

## User Stories

- **US-1:** Als Pflegekraft möchte ich einen Arztbrief direkt mit der Handykamera erfassen, damit ich nichts abtippen muss.
- **US-2:** Als Pflegekraft möchte ich im Posteingang sehen, welche Dokumente warten, freigegeben oder fehlerhaft sind – und warum.
- **US-3:** Als Betreiber der Demo möchte ich Kosten und Missbrauch begrenzen.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F02-AC1 | Das System soll im Posteingang „Foto aufnehmen“ (Kamera, Rückseite) und „Datei hochladen“ anbieten; erlaubt sind JPEG, PNG und PDF. |
| F02-AC2 | Das System soll über dem Upload dauerhaft den Hinweis „Bitte keine echten Personendaten hochladen.“ anzeigen. |
| F02-AC3 | WENN ein Foto gewählt wird, DANN soll das System es im Browser vor dem Upload auf höchstens 2000 px an der langen Kante verkleinern, die Ausrichtung (EXIF) korrigieren und als JPEG (Qualität 0,85) senden. |
| F02-AC4 | FALLS eine Datei nach der Verkleinerung größer als 4 MB ist, einen anderen Typ hat (geprüft am Inhalt, nicht an der Endung) oder ein PDF mehr als 5 Seiten hat, DANN soll das System sie ohne OCR-Aufruf ablehnen und den Grund verständlich anzeigen. |
| F02-AC5 | WENN eine gültige Datei hochgeladen wird, DANN soll das System Upload-, OCR- und LLM-Kontingent (F10) **vor** der Annahme prüfen und bei Überschreitung mit der Kontingent-Meldung ablehnen; sonst Datei und Dokument (Status `uploaded`) im Wohnbereich der Pflegekraft anlegen und sofort im Posteingang anzeigen. |
| F02-AC6 | WENN ein Dokument angenommen wurde, DANN soll das System im Hintergrund OCR (`processing`) und Feldvorschlag (`extracting`, F03-AC1) ausführen und erst danach `ready_for_review` setzen; der Posteingang aktualisiert den Status ohne Neuladen. |
| F02-AC7 | FALLS die OCR weniger als 80 Zeichen liefert (leere Seite, unscharf, abgeschnitten) oder der Text kein Pflegedokument erkennen lässt (z. B. Kochrezept, Rechnung), DANN soll das System den Status `unreadable` setzen und „Dokument nicht lesbar – bitte neu fotografieren (gerade, hell, ganze Seite)“ bzw. „Kein Pflegedokument erkannt“ anzeigen, ohne Felder vorzuschlagen. |
| F02-AC8 | FALLS OCR oder LLM nicht erreichbar sind, das Kontingent während der Verarbeitung erschöpft ist oder ein Schritt länger als 5 Minuten dauert, DANN soll das System den Status `failed` mit Fehlercode (`ocr_unavailable`, `llm_unavailable`, `quota_exceeded`, `timeout`) setzen, eine passende Meldung zeigen und „Erneut versuchen“ anbieten; ein Neuversuch setzt beim fehlgeschlagenen Schritt fort. |
| F02-AC9 | FALLS die API während der Verarbeitung neu startet, DANN soll das System hängengebliebene Dokumente spätestens beim nächsten Abruf des Posteingangs als `failed`/`timeout` markieren statt sie dauerhaft „in Bearbeitung“ zu zeigen. |
| F02-AC10 | Das System soll pro Login-Sitzung höchstens 5 Uploads zulassen (Zähler an der serverseitigen Sitzungs-ID aus dem BFF-Nachweis, nicht am geteilten Demo-Konto); danach „Upload-Limit erreicht – Musterdokumente bleiben nutzbar“. |
| F02-AC11 | WO `OCR_PROVIDER=docling` gesetzt ist, soll das System Docling statt Mistral OCR nutzen, ohne Codeänderung. |
| F02-AC12 | Das System soll eine PDL beim Upload den Wohnbereich wählen lassen; Pflegekräfte laden immer in ihren eigenen Wohnbereich, eine andere Angabe wird mit 403 abgelehnt. |
| F02-AC13 | Der Posteingang soll nur Dokumente der eigenen Wohnbereiche zeigen, mit Typ (falls erkannt), Uhrzeit, Status-Badge (wartet, in Bearbeitung, bereit zur Prüfung, freigegeben, verworfen, nicht lesbar, Fehler) und Link zur Prüfung (F03). |

## Nicht im Umfang

Injection-Prüfung (F07, Status `suspicious`), Pseudonymisierung (F06), mehrseitige Bildserien (ein Foto = eine Seite).
