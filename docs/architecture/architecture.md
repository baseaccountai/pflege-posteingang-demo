# Architektur „Pflege-Posteingang“ (arc42, schlank)

Stand: 25.10.2026 · Quelle: [Design-Dokument](../superpowers/specs/2026-10-23-pflege-posteingang-demo-design.md)

> Einzige Stelle für die technische Architektur. Entscheidungen im Detail: [ADRs](adr/). Diagramme: [diagrams/context.md](diagrams/context.md).

## 1. Einführung und Ziele

Digitaler Posteingang einer Pflegeeinrichtung: Papierdokumente (Arztbrief, Medikationsplan, Überleitungsbogen) werden per OCR erfasst, KI schlägt strukturierte Felder vor, **ein Mensch gibt frei**, freigegebene Daten landen in der Bewohnerakte. Pflegekräfte stellen Fragen an die Dokumente (RAG) und erhalten Antworten mit Quellen. Ein Agent legt nach Bestätigung Wiedervorlagen an.

Die Anwendung ist eine **Bewerbungsdemo** (Stelle Nr. 479, Projekt KLARA). Sie soll zeigen, wie generative KI datenschutzkonform und mit sichtbarer Sicherheitsarchitektur integriert wird.

**Qualitätsziele**

| Priorität | Ziel | Bedeutung |
|---|---|---|
| 1 | Sicherheit / Datenschutz | Nutzer und Agent sehen nur ihren Wohnbereich (RLS); kein Cloud-Modell außer OCR sieht identifizierende Daten; Prompt-Injection wird erkannt und in ihrer Wirkung begrenzt. |
| 2 | Nachvollziehbarkeit | Jeder Akteneintrag mit Herkunftsdokument; Protokoll für die PDL; Antworten mit Quellen. |
| 3 | Austauschbarkeit | OCR, LLM, Embeddings, IdP per Konfiguration umschaltbar (Cloud ↔ lokal). |
| 4 | Verständlichkeit | In zwei Minuten erkennbar, wo welche Anforderung umgesetzt ist. |

**Randbedingungen:** nur erfundene Musterdaten; Budget ca. 10–15 €; europäische Anbieter bevorzugt (US-Anbieter mit EU-Rechenzentrum akzeptiert); Oberfläche Deutsch, Code Englisch.

## 3. Kontextabgrenzung

| Nachbarsystem | Zweck | Öffentlich | Lokal |
|---|---|---|---|
| Identity Provider (OIDC) | Login, Rollen, Wohnbereich-Claim | Zitadel Cloud | Keycloak |
| OCR | Bild/PDF → Markdown | Mistral OCR | Docling |
| LLM + Embeddings | Feldvorschläge, Antworten, Agent, Vektoren | Mistral (Small, Ministral, mistral-embed) | Ollama |
| Datenplattform | Postgres, pgvector, RLS (Dateien in Postgres, ADR 0010) | Supabase (Irland, `eu-west-1`) | Supabase self-hosted |

Nutzer: Pflegekraft Wohnbereich 1, Pflegekraft Wohnbereich 2, Pflegedienstleitung (PDL). Kontextdiagramm: [diagrams/context.md](diagrams/context.md).

## 5. Bausteinsicht

| Baustein | Technik | Verantwortung |
|---|---|---|
| `apps/web` | Next.js (App Router), Tailwind, shadcn/ui, PWA | Oberfläche; **Backend-for-Frontend**: OIDC-Login serverseitig (Authorization Code + PKCE), Cookie nur mit Sitzungs-ID, Tokens serverseitig in Postgres (ADR 0009), Weiterleitung an die API mit BFF-Nachweis. Tokens gelangen nie in den Browser. |
| `apps/api` | Python, FastAPI | **Sicherheitsschicht**: Token prüfen, Rechte ableiten, pseudonymisieren, Injection filtern, LLM/OCR aufrufen, protokollieren. Anbieter hinter Schnittstellen. |
| `apps/api/security/` | Python | Prompt-Injection-Erkennung (Muster getrennt vom Testkorpus), Pseudonymisierung. |
| `supabase/` | SQL-Migrationen, Seed | Tabellen, pgvector, **RLS-Policies** pro Wohnbereich, Musterdaten. |
| `infra/` | Docker Compose, Keycloak-Realm | Lokaler Betrieb inkl. lokalem LLM (Profil `local-llm`). |

## 6. Laufzeitsicht

**Dokument einlesen:** Foto/PDF → OCR (Markdown) → **lokale** Injection-Prüfung (Regeln, versteckter Text; kein Cloud-Modell) → Pseudonymisierung (ab Stufe 2) → Klassifikator (öffentlich: Ministral, sieht nur pseudonymisierten Text) → verdächtige Abschnitte markiert, nicht indiziert → KI-Feldvorschlag → **menschliche Freigabe** inkl. Bestätigung des Bewohners → Chunking (strukturbasiert, Tabellen ganz, Recursive Splitting als Rückfall) → Embeddings → pgvector mit Metadaten (Bewohner, Wohnbereich, Dokumenttyp, Datum, Seite, Dokument-ID).

**Frage stellen (RAG):** Frage → Rechte (RLS, nur eigener Wohnbereich) → Vektorsuche (optional pro Bewohner) → Pseudonymisierung → LLM → Ausgabe prüfen, zurückübersetzen, Quellen anhängen → Protokoll.

**Agent-Aktion:** Nutzer-Token → Token Exchange (RFC 8693) → kurzlebiges Agenten-Token (`act`-Claim, Scopes lesen + Wiedervorlage anlegen, Wohnbereich des Nutzers) → Werkzeugaufruf → schreibende Aktion nur nach Bestätigung durch den Menschen. Rückfall: Backend stellt ein selbst signiertes, gleich eingeschränktes Agenten-JWT aus.

## 7. Verteilungssicht

| Umgebung | Web | API | Daten | IdP | KI |
|---|---|---|---|---|---|
| Öffentlich | Vercel | Vercel `fra1`, eigenes Projekt (ADR 0011) | Supabase Irland (`eu-west-1`) | Zitadel Cloud | Mistral |
| Lokal | Docker | Docker | Supabase self-hosted | Keycloak (Docker) | Ollama + Docling (Docker) |

Gleiche Architektur in beiden Umgebungen, nur andere Anbieter. CI/CD: GitHub Actions (Tests, Deployment, Keep-alive, nächtlicher Reset).

## 8. Querschnittliche Konzepte – Sicherheit

| Konzept | Umsetzung |
|---|---|
| Authentifizierung | OIDC Authorization Code + PKCE über den BFF; Demo-Konten ohne Admin-Rechte. |
| Token-Prüfung | Signatur via JWKS, `iss`, `aud`, `exp`, feste Algorithmen. |
| Autorisierung | Supabase **Row Level Security**; Backend greift **im Namen des Nutzers/Agenten** zu, Service-Key nur für Seed/Reset. |
| Agenten-Rechte | Eigenes, kurzlebiges Token; nie mehr Rechte als der Nutzer; Schreiben nur nach Bestätigung; verbotene Aktionen existieren nicht als Werkzeug. |
| Pseudonymisierung | Nach OCR, vor Feldextraktion, Embeddings und Chat (z. B. Presidio); Zuordnung nur im Backend. **Grenze:** Cloud-OCR sieht Rohdaten – lokal (Docling) nicht. |
| Prompt-Injection | Fünf Schichten: Dokument prüfen, Klassifikator, Prompt-Aufbau mit Daten-Markierung, minimale Rechte, Ausgabeprüfung. Siehe [Bedrohungsmodell](../security/threat-model.md). |
| Missbrauch/Kosten | Upload-Limit pro Sitzung, Tagesobergrenze für Mistral-Aufrufe, nächtlicher Reset. |

## 9. Architekturentscheidungen

| ADR | Entscheidung |
|---|---|
| [0001](adr/0001-python-fastapi-backend.md) | Python/FastAPI als Backend |
| [0002](adr/0002-supabase-platform.md) | Supabase als Datenplattform |
| [0003](adr/0003-mistral-cloud-ollama-local.md) | Mistral öffentlich, Ollama/Docling lokal |
| [0004](adr/0004-nextjs-bff.md) | Next.js als Backend-for-Frontend |
| [0005](adr/0005-zitadel-public-keycloak-local.md) | Zitadel öffentlich, Keycloak lokal |
| [0006](adr/0006-kiro-spec-format.md) | Spec-Format im Kiro-Stil |
| [0007](adr/0007-db-access-on-behalf-of-user.md) | Datenbankzugriff im Namen des Nutzers (Login-Rolle + `set local role`, Spike F01) |
| [0008](adr/0008-minimal-service-worker.md) | Eigener minimaler Service Worker mit Allowlist |
| [0009](adr/0009-server-side-sessions.md) | Login-Sitzung serverseitig in Postgres |
| [0010](adr/0010-files-in-postgres.md) | Originaldateien in Postgres statt Supabase Storage |
| [0011](adr/0011-api-on-vercel.md) | API auf Vercel statt Koyeb (Koyeb-Übernahme durch Mistral, kein günstiger Tarif mehr) |

## 11. Risiken und technische Schulden

| Risiko | Gegenmaßnahme |
|---|---|
| Supabase pausiert nach einer Woche Inaktivität; Backend schläft | Keep-alive per GitHub Action; Hinweis „Demo startet …“ |
| Token Exchange im IdP nicht verfügbar | Rückfall: selbst signiertes Agenten-JWT (ADR) |
| OIDC-Token und Supabase-RLS passen nicht direkt zusammen | Gelöst durch Spike S1: Login-Rolle + Claims pro Transaktion (ADR 0007), lokal und in der Cloud getestet |
| Docling braucht viel RAM | nur lokal; öffentlich Mistral OCR |
| Kostenlose Kontingente ändern sich | Limits beim Anlegen der Konten prüfen |
| Stufe 2 (Sicherheitskern) wird nicht fertig | Stufe 1 bis 02.11. online; Stufe 2 vor Feinschliff |
