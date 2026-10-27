# ADR 0011: API auf Vercel statt Koyeb

Status: angenommen · Datum: 27.10.2026 · ersetzt die Hosting-Angabe „Koyeb Frankfurt“ in Design, Architektur und F11

## Kontext
Die FastAPI-API (`apps/api`) sollte öffentlich auf einer kleinen bezahlten Koyeb-Instanz in Frankfurt (≥ 2 GB RAM) laufen. Beim Anlegen des Kontos (27.10.2026) zeigte sich:

| Befund | Quelle |
|---|---|
| Mistral AI hat Koyeb im Februar 2026 übernommen; Koyeb richtet sich seitdem an Unternehmenskunden. | TechCrunch, 17.02.2026 |
| Der Starter-Tarif (nur Verbrauch) ist für **neue** Konten geschlossen; neue Organisationen starten im Pro-Tarif (**29 $/Monat + Rechenzeit**), Kreditkarte Pflicht. | Koyeb-Preisseite, Presseberichte |
| Eco-Instanzen wären günstig (eco-medium: 1 vCPU, 2 GB, 10,71 $/Monat, Frankfurt), aber nur zusammen mit einem Tarif. | Koyeb-Doku „Instances“ |

Mit Pro-Tarif läge das API-Hosting allein bei ca. 29 $ – mehr als das Doppelte dessen, was neben den Mistral-Kosten vom Budget (10–15 € bis zur Bewerbung) übrig ist.

Anforderungen an das API-Hosting (Bestandsaufnahme 27.10.2026): Python/FastAPI, öffentlich per HTTPS, EU-Region, ausgehende Verbindungen zu Supabase (Pooler), Mistral und Zitadel, Geheimnisse als Umgebungsvariablen, Ausrollen aus GitHub Actions für genau einen geprüften Commit, Health-Check, Kosten ≤ ca. 10 €. RAM: heute ≈ 0,5 GB, mit Presidio ≈ 1–1,5 GB.

## Entscheidung
Die API läuft öffentlich als **zweites Vercel-Projekt** (Root `apps/api`, Python-Laufzeit mit FastAPI-Erkennung, Region `fra1`, Hobby-Tarif). Sie bleibt ein eigener Dienst mit eigener Adresse; der BFF ruft sie wie bisher mit Access-Token und BFF-Nachweis auf. Lokal läuft sie unverändert als Docker-Container (`make up`).

Vercel Hobby (Stand 27.10.2026): 2 GB Arbeitsspeicher, bis 300 s je Anfrage, Paketgröße 500 MB, Region wählbar, 0 €.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Koyeb Pro + eco-medium | ca. 29 $/Monat, über dem Budget |
| Hetzner-VPS (4 GB, ca. 5–6 €/Monat) | Server, HTTPS und Updates selbst betreiben; günstige Reihe zeitweise nicht bestellbar. **Rückfallebene**, falls der Spike S5 scheitert. |
| Render (Frankfurt, 2 GB) | ca. 25 $/Monat, über dem Budget |
| Scaleway Serverless Containers / Google Cloud Run | gleiche Serverless-Einschränkungen wie Vercel, aber ein weiteres Konto |

## Konsequenzen
+ 0 € Hosting, kein weiteres Konto; Web und API beim selben Anbieter in derselben Region.
+ Deployment ohne Container-Registry: Vercel baut aus dem Commit.
− **Arbeit nach der Antwort** (FastAPI `BackgroundTasks` nach dem 202 des Uploads) ist auf Vercel nicht zugesichert. Spike S5 prüft das; falls sie abbricht, stößt der Browser die Verarbeitung mit einer eigenen Anfrage an (F02 Aufgabe 10).
− **LLM Guard** (mit PyTorch) passt nicht in 500 MB: Die Injection-Prüfung übernimmt öffentlich ein kleines Mistral-Modell (im Design als Variante vorgesehen); LLM Guard nur lokal (Phase 8). Presidio mit kleinem deutschem Sprachmodell bleibt möglich.
− Kaltstart nach Pausen; der Hinweis „Demo startet …“ und der Keep-alive-Ping bleiben.
− Docker-Kenntnisse zeigt nur noch der lokale Betrieb, nicht das öffentliche Hosting.

## Spike S5 (offen)
Aktuelle API als Vercel-Projekt in `fra1`: `/health`; Login und Bewohnerliste über den BFF (RLS über Pooler, `set local role` je Transaktion); Upload eines Musterdokuments bis `ready_for_review` (läuft `BackgroundTasks` zu Ende?); Kaltstartzeit. Ergebnis wird hier nachgetragen.
