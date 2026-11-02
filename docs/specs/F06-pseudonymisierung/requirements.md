# F06 – Pseudonymisierung vor dem LLM: Anforderungen

Status: freigegeben 29.10.2026 (im Chat) · Stufe: 2 · Bildschirme: 2 (Posteingang), 4 (Fragen) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Außer der OCR soll kein Cloud-Modell die Namen und Geburtsdaten der Bewohner sowie erkennbare weitere Personen- und Kontaktdaten sehen (Design 12, „Pseudonymisierungs-Grenze“). Nach der OCR ersetzt das Backend diese Angaben durch Platzhalter wie `Bewohner_A17`, **bevor** Feldvorschlag (F03), Embeddings (F05) und Chat-LLM (F05, F08) den Text sehen. Die Zuordnung bleibt im Backend; Anzeigen werden zurückübersetzt. Rundgang Minute 2: „Das hat das KI-Modell gesehen“.

## User Stories

- **US-1:** Als Pflegekraft möchte ich sehen, was das KI-Modell von meiner Frage und den Quellen bekommen hat, damit ich der Antwort vertrauen kann, ohne dass Namen das Haus verlassen.
- **US-2:** Als Prüfer der Bewerbung möchte ich nachvollziehen, welche Daten an welchen Anbieter gehen (Cloud-OCR sieht Rohdaten, sonst niemand).

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F06-AC1 | Das System soll vor **jedem** Aufruf eines Chat- oder Embedding-Modells (Feldvorschlag F03, Indizierung und Frage F05, Agent F08, Klassifikator F07) den Text durch den Pseudonymisierer leiten; es gibt im Code genau eine Stelle, über die solche Aufrufe laufen. |
| F06-AC2 | Der Pseudonymisierer soll ersetzen: Namen **aller** Bewohner der Einrichtung (Nachname mit Anrede wie „Hr.“, „Frau“, „Herrn“ in beliebiger Schreibweise; ohne Anrede in beliebiger Groß- und Kleinschreibung – das Datenmodell kennt keine Vornamen; geändert nach dem Codex-Review Phase 7, vorher nur großgeschrieben) durch `Bewohner_<Code>`; deren Geburtsdaten (alle gängigen Schreibweisen) durch `Geburtsdatum_<Code>` desselben Bewohners (andere Datumsangaben bleiben, sie sind fachlich nötig); weitere Personennamen nach Anrede oder Titel („Dr. med. Sommer“, „Frau Lindner“) durch `Person_<n>`; Telefonnummern, E-Mail-Adressen, Krankenversichertennummern und Straße + Hausnummer durch `[TELEFON]`, `[E-MAIL]`, `[VERSICHERTENNR]`, `[ADRESSE]`. |
| F06-AC3 | Jeder Platzhalter soll innerhalb eines Aufrufs genau einen Originalwert bezeichnen. Der Code `Bewohner_<Code>` soll pro Bewohner dauerhaft gleich sein (Spalte `residents.pseudonym`, zufällig vergeben, z. B. `A17`) und keinen Rückschluss auf Name, Zimmer oder Wohnbereich erlauben; `Person_<n>` gilt je Dokument bzw. je Frage. |
| F06-AC4 | Chunks (F05) sollen aus pseudonymisiertem Text eingebettet werden; ihr Text bleibt im Original gespeichert (nur für Berechtigte, RLS) und wird vor jedem Modellaufruf erneut pseudonymisiert. Der Bezug zum Bewohner läuft ausschließlich über `resident_id` (Metadaten), nicht über Namen im Text. |
| F06-AC5 | WENN eine Frage einen Bewohnernamen enthält, DANN soll das System den Namen wie bisher auf die Bewohner-ID auflösen (F05-AC6) und an Embedding-Modell und LLM nur die pseudonymisierte Frage geben. |
| F06-AC6 | WENN ein Modell Platzhalter zurückgibt, DANN soll das System sie vor der Anzeige und vor der Belegprüfung (F03 wörtliche Belege) in die Originalwerte zurückübersetzen; unbekannte Platzhalter bleiben sichtbar stehen. |
| F06-AC7 | Die Antwort auf eine Frage soll einen aufklappbaren Bereich „Das hat das KI-Modell gesehen“ haben: pseudonymisierte Frage und pseudonymisierte Quellenauszüge, genau wie gesendet. |
| F06-AC8 | Das System soll die Zuordnung Platzhalter → Original nie an ein Modell senden, nie protokollieren (F12) und nur innerhalb der Rechte des Aufrufers verwenden (RLS: nur Bewohner der eigenen Wohnbereiche werden zurückübersetzt). |
| F06-AC9 | Der Posteingang soll beim Upload zusätzlich zum festen Upload-Hinweis anzeigen: „Die Texterkennung (OCR) läuft öffentlich bei Mistral und sieht das Original; alle weiteren KI-Schritte sehen nur Platzhalter. Im lokalen Betrieb verlässt nichts den Rechner.“ |
| F06-AC10 | FALLS nach der Pseudonymisierung noch ein bekannter Bewohnername oder ein Geburtsdatum eines Bewohners im ausgehenden Text steht, DANN soll das System den Modellaufruf abbrechen (Fehler `pseudonymization_failed`, Ereignis für F12) statt Klartext zu senden. |
| F06-AC11 | Die Seite „Über das Projekt“ soll in einer Tabelle zeigen, welcher Anbieter welche Daten sieht (OCR: Original; Feldvorschlag, Embeddings, Chat, Klassifikator: nur Platzhalter; lokal: alles auf dem Rechner). |
| F06-AC12 | Die Seite „Über das Projekt“ und der Hinweis aus AC9 sollen die Grenze offen nennen: Namen ohne Anrede oder Titel, die nirgends als Bewohner bekannt sind, werden nicht erkannt. |

## Nicht im Umfang

- Microsoft Presidio oder andere NER-Modelle (zu groß für die Vercel-Funktion; bei Musterdaten ist der Abgleich mit bekannten Namen zuverlässiger) – Entscheidung im Design.
- Pseudonymisierung der OCR selbst (braucht das Originalbild; Argument für den lokalen Modus).
- Erkennung beliebiger, nirgends bekannter Namen ohne Anrede oder Titel (offen benannt, AC12).
