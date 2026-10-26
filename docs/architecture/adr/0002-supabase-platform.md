# ADR 0002: Supabase als Datenplattform

Status: angenommen · Datum: 23.10.2026

## Kontext
Benötigt werden relationale Daten (Bewohner, Dokumente, Felder, Wiedervorlagen, Protokoll), Vektorsuche, Dateiablage und **Rechte pro Wohnbereich**, die auch für den KI-Agenten gelten. Öffentlich und lokal soll dieselbe Plattform laufen.

## Entscheidung
**Supabase** (Region EU – geplant Frankfurt, tatsächlich Irland, siehe Nachtrag; lokal self-hosted per Docker): Postgres, **pgvector**, Storage und **Row Level Security**. Das Backend greift **im Namen des Nutzers bzw. Agenten** zu, damit RLS greift; der Service-Key wird nur für Seed und Reset verwendet.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Eigenes Postgres + pgvector | Storage, Auth-Integration und Hosting selbst bauen |
| Separate Vektordatenbank (z. B. Qdrant) | Rechte müssten doppelt gepflegt werden; RLS wirkt dort nicht |
| Rechteprüfung nur im Backend-Code | Ein Fehler im Code würde fremde Wohnbereiche offenlegen; Datenbank-Rechte sind die stärkere Grenze |

## Konsequenzen
+ Rechte in der Datenbank erzwungen, auch für Vektorsuche.
+ Gleiche Plattform öffentlich und lokal.
− Supabase erwartet eigene JWTs; Abbildung der OIDC-Claims (Zitadel/Keycloak) auf RLS-Claims ist ein Spike in F01.
− Kostenloses Projekt pausiert nach einer Woche ohne Aktivität → Keep-alive.

## Nachtrag 25.10.2026
Originaldateien liegen nicht in Supabase Storage, sondern in Postgres (siehe [ADR 0010](0010-files-in-postgres.md)).

## Nachtrag 26.10.2026: Region Irland
Das Projekt wurde versehentlich in `eu-west-1` (Irland) statt `eu-central-1` (Frankfurt) angelegt. Der Bewerber hat entschieden, es dort zu belassen: weiterhin EU-Region und DSGVO-konform. Folge: ca. 20–25 ms zusätzliche Latenz je Datenbankabfrage von Vercel (`fra1`) und Koyeb (Frankfurt). Falls das spürbar wird, kann die Vercel-Funktionsregion auf `dub1` (Dublin) gelegt werden.
