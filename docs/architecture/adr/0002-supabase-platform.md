# ADR 0002: Supabase als Datenplattform

Status: angenommen · Datum: 23.10.2026

## Kontext
Benötigt werden relationale Daten (Bewohner, Dokumente, Felder, Wiedervorlagen, Protokoll), Vektorsuche, Dateiablage und **Rechte pro Wohnbereich**, die auch für den KI-Agenten gelten. Öffentlich und lokal soll dieselbe Plattform laufen.

## Entscheidung
**Supabase** (Region Frankfurt; lokal self-hosted per Docker): Postgres, **pgvector**, Storage und **Row Level Security**. Das Backend greift **im Namen des Nutzers bzw. Agenten** zu, damit RLS greift; der Service-Key wird nur für Seed und Reset verwendet.

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
