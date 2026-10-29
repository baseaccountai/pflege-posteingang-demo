# F06 – Pseudonymisierung vor dem LLM: Design

## Überblick

Ein Modul `app/privacy/` liegt zwischen den Fachfunktionen und allen Modell-Anbietern (außer OCR). Es baut pro Aufruf eine **Zuordnung** (Platzhalter ↔ Original) aus zwei Quellen:

1. **Bekannte Personen** aus der Datenbank: alle Bewohner der Einrichtung mit Namen und Geburtsdatum. Gelesen über eine `security definer`-Funktion `app.pseudonym_directory()`, die nur `(pseudonym, Namensvarianten, Geburtsdatum)` liefert – auch Bewohner fremder Wohnbereiche, damit ein Name aus WB2 in einem WB1-Dokument ebenfalls ersetzt wird. **Ausführbar nur für die Login-Rolle `api_gateway`** und nur **außerhalb** von `as_principal` (vor `set role authenticated`); `authenticated` – also jeder Fach-Principal, Mensch wie Agent – hat kein `execute`. Das Verzeichnis wird bei jeder Verwendung frisch gelesen (Umsetzung: ein Zwischenspeicher hätte neue Bewohner bis zu 60 s ungeschützt gelassen). Zurückübersetzt werden nur Bewohner, die der Aufrufer per RLS sehen darf (AC8); fremde bleiben `Bewohner_<Code>`.
2. **Regeln** für weitere Personen nach Anrede/Titel und für Kontaktdaten (AC2).

Ablauf (Design 5.4, ergänzt):

```
OCR (Original) → ocr_pages (Original, für die Prüfansicht)
              → Pseudonymisierer → Feldvorschlag-LLM → Antwort in Platzhalterform → Belegprüfung (F03)
                gegen den gesendeten Text → Rückübersetzung
Freigabe      → Chunking → chunks.content (Original) ; Pseudonymisierer → Embeddings
Frage         → Namen → resident_id (F05-AC6) → Pseudonymisierer → Embedding + LLM
              → Rückübersetzung → Anzeige (+ „Das hat das KI-Modell gesehen“)
```

**Eine Tür zu den Modellen (AC1):** Die Anbieter-Schnittstellen `LlmProvider` und `EmbeddingProvider` werden nur noch über `app/privacy/gateway.py` (`ModelGateway`) aufgerufen; ein Architekturtest prüft per Import-Analyse, dass außer dem Gateway kein Modul die Anbieter direkt nutzt. Das Gateway führt die Prüfung AC10 (kein bekannter Name, kein Geburtsdatum mehr im ausgehenden Text) vor jedem Aufruf aus.

**Ersetzungsreihenfolge:** längste Treffer zuerst (Vorname + Nachname vor Nachname), Wortgrenzen beachten, Bindestrich-Namen ganz („Muster-Bauer“). Geburtsdaten in `TT.MM.JJJJ`, `T.M.JJ`, `JJJJ-MM-TT`, „12. März 1938“. Versichertennummer: Buchstabe + 9 Ziffern. Kontaktdaten bekommen nummerierte Platzhalter (`[TELEFON_1]`, `[E-MAIL_1]`, `[VERSICHERTENNR_1]`, `[ADRESSE_1]`). Telefon: Ziffernfolgen ab 6 Ziffern mit `+49`/`0`-Präfix, Leerzeichen, `/`, `-`. Adresse: `<Wort>(straße|str.|weg|platz|allee|gasse) <Nr>`.

**Belegprüfung (Umsetzung 29.10.2026):** Die wörtlichen Belege (F03-AC3) werden gegen genau den pseudonymisierten Text geprüft, den das Modell bekam; die Modellantwort wird dafür mit derselben Zuordnung in Platzhalterform gebracht. Erst danach wird zurückübersetzt. Würde man erst zurückübersetzen und gegen das Original prüfen, scheiterte die Prüfung an Schreibvarianten („Herrn Muster-Bauer“ vs. „Hr. Muster-Bauer“). Fehlerfall: `documents.error_code = pseudonymization_failed`.

## Komponenten

| Komponente | Ort | Verantwortung |
|---|---|---|
| Pseudonymisierer | `apps/api/app/privacy/pseudonymizer.py` | Text + Verzeichnis → (pseudonymisierter Text, Zuordnung); Rückübersetzung |
| Regeln | `apps/api/app/privacy/patterns.py` | Anrede/Titel, Datum, Telefon, E-Mail, Versichertennr., Adresse |
| Gateway | `apps/api/app/privacy/gateway.py` | einzige Tür zu LLM/Embeddings; Abbruch nach AC10; liefert „gesendet“-Ansicht (AC7) |
| Anpassungen | `extraction/service.py`, `rag/indexer.py`, `rag/routes.py` | nutzen das Gateway; F03-Belegprüfung nach Rückübersetzung |
| Anzeige | `apps/web/src/components/question-chat.tsx` | aufklappbarer Bereich „Das hat das KI-Modell gesehen“ |
| Hinweise | Posteingang, `/projekt` | AC9, AC11 |

## Datenmodell

| Tabelle | Änderung | RLS-Policy |
|---|---|---|
| `residents` | + `pseudonym text not null unique` (z. B. `A17`; zwei Zeichen + zwei Ziffern, zufällig, im Seed fest) | unverändert |
| – | Funktion `app.pseudonym_directory()` `security definer`, `stable`: liefert für **alle** Bewohner `pseudonym`, `display_name`, Namensteile, `birth_date`; `execute` nur für `api_gateway`, ausdrücklich nicht für `authenticated`/`anon` | Funktion umgeht RLS bewusst nur für diese drei Angaben und nur für die Backend-Rolle; dokumentiert im Bedrohungsmodell |
| `chunks` | `content` bleibt im Original (Umsetzung 29.10.2026: so lassen sich auch `Person_n` in Antworten zurückübersetzen, weil die Zuordnung je Frage neu entsteht); die Vektoren stammen aus pseudonymisiertem Text. Besucher-Dokumente löscht der nächtliche Reset; die Seed-Chunks (`04_chunks.sql`) erzeugt der Bewerber neu (`make seed-chunks`) | unverändert |

Die Zuordnung je Aufruf wird **nicht** gespeichert (nur im Speicher der Anfrage).

## Schnittstellen (API)

| Methode | Pfad | Änderung |
|---|---|---|
| POST | `/questions` | Antwort + `sent_to_model: {question, sources: [{n, text}]}` (pseudonymisiert, AC7) |
| – | Fehler | `pseudonymization_failed` (500, Text „Die Anfrage wurde aus Datenschutzgründen nicht gesendet.“) |

## Sicherheitsaspekte

- **LLM02 Offenlegung:** Modelle sehen nur Platzhalter; Klartext-Prüfung vor dem Senden (AC10) als zweite Schicht.
- **`pseudonym_directory` umgeht RLS:** nur die Backend-Login-Rolle darf es aufrufen, kein Fach-Principal (Test: `authenticated` bekommt `permission denied`). Es liefert Namen/Geburtsdaten fremder Bewohner nur an das Backend (nie an Browser oder Modell). Rückübersetzung prüft RLS. Restrisiko (kompromittiertes Backend) im Bedrohungsmodell.
- **Eindeutige Platzhalter:** `Bewohner_<Code>`, `Geburtsdatum_<Code>`, `Person_<n>`, `[TELEFON_<n>]` usw. sind je Aufruf eindeutig nummeriert, damit die Rückübersetzung nie raten muss.
- **Pseudonym-Code:** zufällig, kein Hash des Namens (sonst per Wörterbuch umkehrbar).
- **Grenze:** Namen ohne Anrede, die nirgends bekannt sind, bleiben stehen – offen benannt (Nicht im Umfang).

## Tests je Ebene

| Ebene | Werkzeug | Abgedeckte Kriterien |
|---|---|---|
| Unit Backend | pytest | AC2, AC3, AC6, AC10 (Tabellen mit Schreibweisen, Bindestrich, Groß/klein, Rückübersetzung, unbekannte Platzhalter) |
| Architektur | pytest (Import-Analyse) | AC1 |
| RLS / Rechte | pytest gegen lokales Supabase | AC3, AC8 (`pseudonym_directory` nur Pseudonym/Name/Geburtsdatum; `authenticated` darf es nicht aufrufen; Rückübersetzung nur eigener WB) |
| Integration | pytest + respx (Fake-LLM zeichnet gesendeten Text auf) | AC1, AC4, AC5, AC10 (kein Klarname in irgendeinem ausgehenden Aufruf: Feldvorschlag, Indizierung, Frage) |
| Unit Web | Vitest | AC7, AC9, AC12 |
| End-to-End | Playwright | AC7 (Bereich aufklappen, Platzhalter sichtbar, kein Klarname darin), AC11 |
