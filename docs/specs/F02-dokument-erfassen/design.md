# F02 – Dokument erfassen: Design

## Ablauf

```
Web (Posteingang) ──multipart──▶ BFF /api/documents ──▶ API POST /documents
   API: Datei prüfen (Magic Bytes, Größe, Seiten) → Quote prüfen (app.consume_quota) → Storage → documents(status=uploaded) → 202
   Hintergrund (FastAPI BackgroundTasks): status=processing → OcrProvider.extract() → Plausibilität → ready_for_review | unreadable | failed
Web pollt GET /documents?status=… alle 3 s, solange etwas in Bearbeitung ist
```

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Upload-UI | `apps/web/src/app/posteingang/page.tsx`, `components/upload-card.tsx` | `<input type="file" accept="image/*,application/pdf" capture="environment">` + Datei-Upload, Hinweistext, Fortschritt |
| Posteingangsliste | `components/inbox-list.tsx` | Status-Badges, Polling |
| Upload-Endpunkt | `apps/api/app/documents/routes.py` | Validierung, Speicher, Anlage, 202 |
| Dateiprüfung | `apps/api/app/documents/validation.py` | Magic Bytes (`%PDF`, JPEG `FFD8FF`, PNG `89504E47`), Größe, Seitenzahl (`pypdf`) |
| OCR-Schnittstelle | `apps/api/app/providers/ocr/base.py` | `class OcrProvider(Protocol): async def extract(file: bytes, mime: str) -> OcrResult` (Seiten mit Markdown) |
| Mistral OCR | `providers/ocr/mistral.py` | Mistral-OCR-API (Modell aus Konfiguration, z. B. `mistral-ocr-latest`), Timeout 60 s |
| Docling | `providers/ocr/docling.py` | Aufruf eines lokalen Docling-Serve-Containers (Phase 8; in Stufe 1 nur Schnittstelle + Test-Attrappe) |
| Auswahl | `providers/ocr/__init__.py` | Fabrik nach `OCR_PROVIDER` |
| Plausibilität | `apps/api/app/documents/readability.py` | < 80 Zeichen → unlesbar; keine Pflege-Schlüsselwörter (Liste: Diagnose, Medikation, mg, Arzt, Patient, Bewohner, Entlassung, …) → unlesbar |

## Datenmodell

Migration `<ts>_f02_documents.sql`: Tabelle `documents`, Enum-Typen `doc_type`, `document_status`; Policies `select/insert/update` mit `ward_id = any(app.ward_ids())`; Storage-Bucket `documents` (privat) mit Policies auf das erste Pfadsegment. Speicherzugriff vom Backend über die Storage-API **mit einem aus den Claims erzeugten, kurzlebigen Nutzer-JWT** – oder, falls der Spike F01 zeigt, dass das nicht ohne JWT-Secret geht, über Postgres-Funktionen; Entscheidung in ADR 0007.

## Schnittstellen (API)

| Methode | Pfad | Request | Response |
|---|---|---|---|
| POST | `/documents` | multipart `file`, optional `ward_id` (nur PDL) | 202 `{id, status}` · 413/415/422 mit `{error_code, message}` · 429 Quote |
| GET | `/documents` | `?status=` | Liste (eigene WB) |
| GET | `/documents/{id}` | – | Dokument inkl. `ocr_markdown`, 404 wenn fremd/nicht vorhanden |
| POST | `/documents/{id}/retry` | – | 202, nur bei `failed` |
| GET | `/documents/{id}/file` | – | Original (Streaming) für die Prüfansicht |

## Sicherheitsaspekte

- Inhaltstyp über Magic Bytes, nicht über Endung/`Content-Type` (AC3).
- Kein OCR-Aufruf vor bestandener Prüfung und Quote (Kostenschutz, AC3, AC8).
- Upload-Zähler: Der BFF erzeugt beim Login eine zufällige `sid` (in der verschlüsselten Session) und sendet sie als Header `X-Session-Id`; die API zählt `usage_counters(kind='upload', subject=sid)`. Der Header ist nur ein Zähler-Schlüssel, keine Berechtigung.
- Speicherpfad aus `ward_id` des Principals, nicht aus Client-Angaben (außer PDL mit Prüfung gegen `ward_ids`).
- Cloud-OCR sieht Rohdaten – bekannte Grenze, Hinweis in der App (F06) und im Bedrohungsmodell.

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest | AC3 (Dateiprüfung mit Beispieldateien), AC6 (Plausibilität), AC9 (Fabrik) |
| Integration | pytest + OCR-Attrappe + lokales Supabase | AC4, AC5, AC7 (Attrappe wirft Fehler), AC8, AC10, AC11 |
| Unit Web | Vitest | AC1 (`accept`, `capture`), AC2 (Text exakt) |
| End-to-End | Playwright (desktop + mobile), API mit OCR-Attrappe | AC4, AC5, AC6 mit `samples/bad/*` |
| Realtest (manuell, klein) | echte Mistral-OCR mit 3 Musterdokumenten | Markdown enthält Medikamententabelle |
