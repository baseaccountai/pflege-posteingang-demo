# F02 – Dokument erfassen: Design

## Ablauf

```
Browser: Foto → verkleinern (canvas, ≤ 2000 px, JPEG 0,85) ──multipart ≤ 4 MB──▶ BFF POST /api/documents (Origin-Prüfung)
  ──▶ API POST /documents
      1. Wartung? → 503              2. Datei prüfen (Magic Bytes, Größe, Seiten)
      3. Kontingente atomar buchen: upload (Sitzung), ocr_page×Seiten (global), llm_call×1 (global) → sonst 429
      4. documents + document_files in einer Transaktion (as_principal) → 202 {id, status: uploaded}
  Hintergrund (BackgroundTasks, gleicher Prozess):
      processing → OcrProvider.extract → Lesbarkeit → extracting → Extraktion (F03) → ready_for_review
Browser pollt GET /documents alle 3 s, solange Einträge in uploaded/processing/extracting sind
```

Vercel begrenzt Anfragen auf 4,5 MB; deshalb gilt 4 MB als Obergrenze nach der Verkleinerung (Reserve für Multipart).

## Zustandsautomat `documents.status`

| Von | Nach | Auslöser |
|---|---|---|
| – | `uploaded` | Annahme (AC5) |
| `uploaded` | `processing` | Hintergrund startet OCR |
| `processing` | `extracting` | OCR lesbar, `ocr_pages` gespeichert |
| `processing` | `unreadable` | Lesbarkeitsprüfung negativ (Endzustand) |
| `extracting` | `ready_for_review` | Vorschlag gespeichert (auch „kein Vorschlag möglich“, F03-AC2) |
| `uploaded` \| `processing` \| `extracting` | `failed` | Fehler, Kontingent erschöpft, Zeitüberschreitung (`error_code`) |
| `failed` | `processing` \| `extracting` | Neuversuch: weiter beim fehlgeschlagenen Schritt (OCR-Ergebnis bleibt erhalten); bucht Kontingent erneut |
| `ready_for_review` | `approved` \| `rejected` | F03 (Endzustände, danach unveränderlich) |

`status_changed_at` und `attempts` werden bei jedem Wechsel gesetzt. **Hängen-Erkennung (AC9):** `GET /documents` markiert vorher Dokumente in `uploaded` (älter als 2 min – Absturz zwischen Annahme und Start der Hintergrundaufgabe) und in `processing`/`extracting` (älter als 5 min) als `failed`/`timeout`; derselbe Abgleich läuft beim Start der API. Ein Neuversuch eines aus `uploaded` gefallenen Dokuments beginnt bei der OCR.

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Upload-UI | `apps/web/src/app/posteingang/page.tsx`, `components/upload-card.tsx` | `<input type="file" accept="image/jpeg,image/png,application/pdf" capture="environment">`, Hinweistext, Fortschritt |
| Bildverkleinerung | `apps/web/src/lib/image/downscale.ts` | `createImageBitmap(file, {imageOrientation: "from-image"})` → Canvas → `toBlob("image/jpeg", 0.85)` |
| Posteingangsliste | `components/inbox-list.tsx` | Status-Badges, Fehlermeldungen je `error_code`, Polling |
| Upload-Endpunkt | `apps/api/app/documents/routes.py` | Ablauf oben |
| Dateiprüfung | `apps/api/app/documents/validation.py` | Magic Bytes (`%PDF`, `FFD8FF`, `89504E47`), Größe, Seitenzahl (`pypdf`) |
| Verarbeitung | `apps/api/app/documents/pipeline.py` | Zustandsautomat, Fortsetzen nach Fehler, Hängen-Erkennung |
| OCR-Schnittstelle | `apps/api/app/providers/ocr/base.py` | `OcrProvider.extract(file, mime) -> OcrResult(pages=[Page(number, markdown)])` |
| Mistral OCR | `providers/ocr/mistral.py` | Mistral-OCR-API (`MISTRAL_OCR_MODEL`), Timeout 60 s, Datei als Base64-Data-URL |
| Docling | `providers/ocr/docling.py` | Stufe 1 nur Schnittstelle + Attrappe; Anbindung Phase 8 |
| Lesbarkeit | `apps/api/app/documents/readability.py` | < 80 Zeichen → `unreadable`; weniger als 2 Treffer aus der Pflege-Wortliste (Diagnose, Medikation, mg, Arzt, Bewohner, Patient, Entlassung, Pflege, Dosierung, Befund, …) → `unreadable` mit Grund „kein Pflegedokument“ |

## Datenmodell

Migration `<ts>_f02_documents.sql`: `documents`, `document_files` (siehe Datenmodell), Aufzählungstypen, zusammengesetzte Fremdschlüssel, Policies `select/insert/update` je Wohnbereich, Trigger gegen Änderung von `ward_id`. Dateien werden **nur** über die API ausgeliefert (`GET /documents/{id}/file`, RLS).

## Schnittstellen (API)

| Methode | Pfad | Request | Response |
|---|---|---|---|
| POST | `/documents` | multipart `file`, optional `ward_id` (nur PDL) | 202 `{id, status}` · 413/415/422 `{error_code, message}` · 403 fremder WB · 429 `{error_code: session_upload_limit \| daily_quota}` · 503 Wartung |
| GET | `/documents` | `?status=` | Liste (eigene WB) inkl. `error_code` |
| GET | `/documents/{id}` | – | Dokument inkl. `ocr_pages` · 404 fremd/unbekannt |
| POST | `/documents/{id}/retry` | – | 202 · 409 wenn nicht `failed` · 429 |
| GET | `/documents/{id}/file` | – | Original mit `Content-Type` aus der Prüfung, `Content-Disposition: inline`, `X-Content-Type-Options: nosniff` |

## Sicherheitsaspekte

- Inhaltstyp über Magic Bytes, Auslieferung nur mit geprüftem Typ (AC4).
- Kein OCR-/LLM-Aufruf vor Prüfung und Kontingentbuchung (AC4, AC5).
- Wohnbereich aus dem Principal; PDL-Angabe gegen `ward_ids` geprüft (AC12).
- Sitzungs-ID für den Zähler stammt aus dem signierten BFF-Nachweis, nicht aus einem frei setzbaren Header (AC10, F01-AC8).
- Cloud-OCR sieht Rohdaten – bekannte Grenze, Hinweis in der App (F06) und im Bedrohungsmodell.

## Tests je Ebene

| Ebene | Werkzeug | Kriterien |
|---|---|---|
| Unit Backend | pytest | AC4 (Beispieldateien, falscher Inhalt mit `.pdf`-Endung), AC7 (leer, 50 Zeichen, Kochrezept, Rechnung), AC11 |
| Integration | pytest + OCR-/LLM-Attrappen + lokales Supabase | AC5 (Kontingent vor Annahme), AC6 (Statusfolge), AC8 (je Fehlercode, Neuversuch setzt richtig fort), AC9 (alter Zeitstempel in `uploaded`, `processing`, `extracting` → `timeout`; Neuversuch aus `uploaded`-Absturz startet OCR), AC10, AC12, AC13 |
| Unit Web | Vitest | AC1 (`accept`, `capture`), AC2 (Text exakt), AC3 (Verkleinerung: 4000×3000 → 2000×1500, Ausrichtung) |
| End-to-End | Playwright (desktop + mobile), API mit Attrappen | AC5, AC6; `samples/bad/` (leer, unscharf, schief, Nicht-Pflegedokument) → passende Meldung |
| Realtest (manuell, klein) | echte Mistral-OCR mit 3 Musterdokumenten + schiefem Foto | Markdown enthält Medikamententabelle |
