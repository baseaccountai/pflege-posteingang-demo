# F04 – Bewohnerakte mit Herkunft: Anforderungen

Status: Entwurf (überarbeitet nach Codex-Review) · Stufe: 1 · Bildschirme: 6 (Bewohnerliste), 7 (Bewohnerakte) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Freigegebene Daten werden pro Bewohner angezeigt – **jeder Eintrag mit Herkunft** (Dokument, Datum, freigegeben von). Grundlage: Design 2, 6 (Bildschirme 6, 7), Mockup `bewohnerakte.html`.

## User Stories

- **US-1:** Als Pflegekraft möchte ich auf einen Blick sehen, bei welchen Bewohnern sich etwas geändert hat oder Wiedervorlagen fällig sind.
- **US-2:** Als Pflegekraft möchte ich bei jeder Medikation sehen, aus welchem Dokument sie stammt und wer sie freigegeben hat.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F04-AC1 | Die Bewohnerliste soll nur Bewohner der eigenen Wohnbereiche zeigen (PDL: alle, gruppiert nach Wohnbereich), mit Name, Zimmer und Wohnbereich. |
| F04-AC2 | Die Bewohnerliste soll je Bewohner ein Badge „Neu“ zeigen, wenn in den letzten 7 Tagen ein Dokument freigegeben wurde, und die Anzahl offener Wiedervorlagen (fällige rot hervorgehoben). |
| F04-AC3 | Die Bewohnerakte soll die Abschnitte Medikation, Diagnosen, Wiedervorlagen und Dokumente zeigen. |
| F04-AC4 | Die Medikation soll aktive Medikamente mit Dosierung (morgens/mittags/abends/nachts) zeigen, Medikamente mit einem Ereignis `new` bzw. `changed` der letzten 7 Tage als „neu“ bzw. „geändert (vorher: …)“ markieren und abgesetzte Medikamente der letzten 30 Tage durchgestrichen mit „abgesetzt am … laut <Dokument>“ zeigen. |
| F04-AC5 | Jeder Eintrag in Medikation, Diagnosen und Wiedervorlagen soll seine Herkunft zeigen: Dokumenttyp, Dokumentdatum (verlinkt auf das Dokument) und „freigegeben von <Rolle> am <Datum>“; bei Medikamenten die Herkunft der **letzten** Änderung, die vollständige Ereignisfolge (angesetzt → geändert → abgesetzt) aufklappbar. |
| F04-AC6 | WENN ein Eintrag `actor_type='agent'` hat, DANN soll das System „vom Agenten angelegt · bestätigt von <Rolle>“ anzeigen. |
| F04-AC7 | Die Bewohnerakte soll einen Knopf „Fragen zu diesem Bewohner“ bieten, der die Fragen-Seite (F05) mit diesem Bewohner als Filter öffnet. |
| F04-AC8 | Das System soll eine offene Wiedervorlage als erledigt markieren lassen (Status `done`, mit Nutzer und Zeitpunkt). |
| F04-AC9 | WENN eine Bewohner-ID fremd oder unbekannt ist, DANN soll das System Bildschirm 8 zeigen (siehe F01-AC10). |
| F04-AC10 | Die Dokumentliste der Akte soll freigegebene Dokumente mit Typ und Datum zeigen und das Original in einer Vorschau öffnen. |

## Nicht im Umfang

Bearbeiten/Löschen von Einträgen, Verlauf/Versionierung, Pflegeplanung.
