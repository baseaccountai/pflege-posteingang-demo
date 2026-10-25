# Fxx – <Feature-Name>: Design

## Überblick

<Wie das Feature umgesetzt wird; Verweis auf Architektur-Abschnitte.>

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|

## Datenmodell

| Tabelle | Spalten | RLS-Policy |
|---|---|---|

## Schnittstellen (API)

| Methode | Pfad | Request | Response | Rechte |
|---|---|---|---|---|

## Sicherheitsaspekte

- <Bedrohung → Gegenmaßnahme; Verweis auf docs/security/threat-model.md>

## Tests je Ebene

| Ebene | Werkzeug | Abgedeckte Kriterien |
|---|---|---|
| Unit Backend | pytest | |
| Unit Web | Vitest | |
| RLS / Rechte | pytest gegen lokales Supabase | |
| Integration | pytest + TestClient | |
| End-to-End | Playwright (desktop + mobile) | |
