# F09 – Anforderungs-Landkarte: Anforderungen

Status: Entwurf · Stufe: 1 · Bildschirm: 1 (Start)

## Einführung

Wer den Link öffnet, soll **in zwei Minuten** erkennen, wo die Anforderungen der Stelle („Sie verfügen über …“) umgesetzt sind. Die Startseite ist deshalb eine Landkarte mit Sprüngen in App und Repo. Grundlage: Design 1 (Erfolg, Anti-Ziele), 6, 8.3.

## User Stories

- **US-1:** Als Professor möchte ich auf der Startseite die Anforderungen der Stelle sehen und mit einem Klick dorthin springen, wo sie umgesetzt sind.
- **US-2:** Als Leser möchte ich die Projektbeschreibung jederzeit erreichen.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F09-AC1 | Die Startseite soll ganz oben eine Karte „Über das Projekt“ zeigen (ein Satz Zweck + Link `/projekt`), oberhalb der Anforderungs-Landkarte. |
| F09-AC2 | Die Kopfzeile soll auf jeder Seite (Handy und Desktop) einen Link „Über das Projekt“ enthalten. |
| F09-AC3 | Die Landkarte soll jede Anforderung aus Design-Abschnitt 1 als Eintrag zeigen: Anforderungstext, Kennzeichnung „gefordert“ oder „wünschenswert“, kurze Beschreibung der Umsetzung, Link in die App (falls vorhanden) und Link ins Repo (Datei/Ordner auf GitHub). |
| F09-AC4 | WENN ein Feature noch nicht umgesetzt ist, DANN soll der Eintrag „in Arbeit (Stufe 2)“ zeigen statt eines toten Links. |
| F09-AC5 | Die Inhalte der Landkarte sollen aus einer einzigen Datendatei (`apps/web/src/content/requirements-map.ts`) stammen; jeder App-Link soll auf eine existierende Route zeigen. |
| F09-AC6 | Die Startseite soll den Rollenwechsel (F01-AC1, F01-AC2) unterhalb der Landkarte anzeigen, mit dem Hinweis, dass alle Daten erfundene Musterdaten sind. |
| F09-AC7 | Die Startseite soll ohne Anmeldung erreichbar sein und ohne laufendes Backend vollständig angezeigt werden (statische Seite). |
| F09-AC8 | Die Seite `/projekt` soll in Stufe 1 einen Platzhalter „Projektbeschreibung folgt“ mit Links zu Architektur, Specs und Repo zeigen (vollständige Fassung in Phase 9). |

## Nicht im Umfang

Projektbeschreibung selbst (Phase 9), Screenshots.
