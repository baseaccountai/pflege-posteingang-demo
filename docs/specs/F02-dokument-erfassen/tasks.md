# F02 – Dokument erfassen: Aufgaben

- [x] **1. Migration `documents` + `document_files`** — `F02-AC5`, `F02-AC12`, `F02-AC13`
  - [x] RLS-Tests: WB2 sieht kein WB1-Dokument/keine WB1-Datei, kann keins in WB1 anlegen, kann `ward_id` nicht ändern, kann keinen WB1-Bewohner referenzieren → rot → Migration → grün · Commit `feat(db): add documents and file storage tables`
- [x] **2. Dateiprüfung** — `F02-AC4`
  - [x] `tests/documents/test_validation.py`: JPEG/PNG/PDF ok; `.pdf`-Endung mit fremdem Inhalt abgelehnt; 4,1 MB abgelehnt; 6-seitiges PDF abgelehnt → rot → `validation.py` → grün · Commit
- [x] **3. OCR-Schnittstelle, Fabrik, Attrappe** — `F02-AC11` · Tests → rot → grün · Commit
- [x] **4. Mistral-OCR-Adapter** — `F02-AC6`, `F02-AC8` · `respx`-Tests: Erfolg → Seiten; 5xx/Timeout → `OcrUnavailable` → rot → grün · Commit
- [x] **5. Lesbarkeit** — `F02-AC7` · Tests: leer, 50 Zeichen, Kochrezept, Rechnung → unlesbar mit Grund; Arztbrief-Auszug → lesbar → rot → grün · Commit
- [x] **6. Verarbeitungs-Pipeline (Zustandsautomat)** — `F02-AC6`, `F02-AC8`, `F02-AC9`
  - [x] Tests mit Attrappen: Erfolgsfolge; OCR-Fehler → `failed/ocr_unavailable` → Neuversuch ab OCR; LLM-Fehler → Neuversuch nur Extraktion; Kontingent leer → `quota_exceeded`; Zeitstempel > 5 min → `timeout` → rot → `pipeline.py` → grün · Commit
- [x] **7. Upload- und Abruf-Endpunkte** — `F02-AC5`, `F02-AC10`, `F02-AC12`, `F02-AC13`
  - [x] Integrationstests: 202; Kontingent leer → 429 ohne OCR-Aufruf; 6. Upload derselben Sitzung → 429, andere Sitzung ok; PDL mit `ward_id`; Pflegekraft mit fremder `ward_id` → 403; Datei-Auslieferung mit Typ-Headern → rot → grün · Commit `feat(api): add document upload with background OCR` (Wartungs-503 folgt mit F10 Aufgabe 6)
- [x] **8. Bildverkleinerung** — `F02-AC3` · Vitest → rot → `downscale.ts` → grün · Commit
- [x] **9. Posteingang-UI** — `F02-AC1`, `F02-AC2`, `F02-AC13`
  - [x] Vitest (Hinweistext exakt, `accept`/`capture`, Meldung je `error_code`) + Playwright (Musterdokument → „bereit zur Prüfung“; vier `samples/bad/`-Fälle → passende Meldung) → rot → grün · Commit `feat(web): add inbox with camera upload`
- [ ] **10. Verarbeitung per Anfrage anstoßen (nur falls Spike S5 zeigt, dass `BackgroundTasks` auf Vercel abbrechen; [ADR 0011](../../architecture/adr/0011-api-on-vercel.md))** — `F02-AC6`, `F02-AC9` · Integrationstests (`/process` führt bis `ready_for_review`, zweiter Aufruf 409, fremd 404, Hängen-Erkennung unverändert) + Playwright (Upload → bereit zur Prüfung) → rot → grün · Commit `feat: process uploads in their own request`
