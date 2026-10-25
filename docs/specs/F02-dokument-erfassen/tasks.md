# F02 – Dokument erfassen: Aufgaben

- [ ] **1. Migration `documents` + Storage** — `F02-AC4`, `F02-AC11`
  - [ ] RLS-Test: WB2 sieht kein WB1-Dokument, kann keins in WB1 anlegen → rot → Migration → grün · Commit `feat(db): add documents table and storage bucket`
- [ ] **2. Dateiprüfung** — `F02-AC1`, `F02-AC3`
  - [ ] `tests/documents/test_validation.py`: JPEG/PNG/PDF ok; `.pdf`-Endung mit EXE-Inhalt abgelehnt; 11 MB abgelehnt; 6-seitiges PDF abgelehnt → rot → `validation.py` → grün · Commit
- [ ] **3. OCR-Schnittstelle + Fabrik + Attrappe** — `F02-AC9`
  - [ ] Test: `OCR_PROVIDER=mistral|docling` liefert passende Klasse; unbekannt → Startfehler → rot → grün · Commit
- [ ] **4. Mistral-OCR-Adapter** — `F02-AC5`, `F02-AC7`
  - [ ] Test mit `respx`-Attrappe der Mistral-API: Erfolg → Seiten-Markdown; 5xx/Timeout → `OcrUnavailable` → rot → grün · Commit
- [ ] **5. Plausibilität** — `F02-AC6`
  - [ ] Test: leerer Text, 50 Zeichen, Kochrezept → unlesbar; Arztbrief-Auszug → lesbar → rot → grün · Commit
- [ ] **6. Upload-Endpunkt + Hintergrundverarbeitung** — `F02-AC4`, `F02-AC5`, `F02-AC7`, `F02-AC8`, `F02-AC10`
  - [ ] Integrationstests: 202 + Status-Verlauf; Fehlerpfad `failed` + Retry; 6. Upload → 429; PDL mit `ward_id`; Pflegekraft mit fremder `ward_id` → 403 → rot → grün · Commit `feat(api): add document upload with background OCR`
- [ ] **7. Posteingang-UI** — `F02-AC1`, `F02-AC2`, `F02-AC11`
  - [ ] Vitest (Hinweistext exakt, `accept`/`capture`) + Playwright (Upload Musterdokument → „wartet auf Prüfung“; `samples/bad/leer.jpg` → „nicht lesbar“) → rot → grün · Commit `feat(web): add inbox with camera upload`
