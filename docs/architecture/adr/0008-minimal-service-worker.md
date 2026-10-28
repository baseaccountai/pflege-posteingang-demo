# ADR 0008: Eigener minimaler Service Worker mit Allowlist

Status: angenommen · Datum: 28.10.2026 · F11-AC2, F11-AC3

## Kontext
Die App soll als PWA installierbar sein und ohne Netz eine verständliche Offline-Seite zeigen. Gleichzeitig enthalten fast alle Antworten Daten der angemeldeten Rolle (Akte, Posteingang, Dokumente, Antworten auf Fragen). Diese dürfen ein Abmelden oder einen Rollenwechsel nicht im Browser-Cache überleben (F01-AC13). Next.js 16 baut mit Turbopack; die üblichen PWA-Bibliotheken (Serwist, next-pwa) hängen sich in den Webpack-Build ein und cachen standardmäßig auch Seiten.

## Entscheidung
Ein eigener Service Worker `apps/web/public/sw.js` (ca. 70 Zeilen, ohne Bibliothek):

| Anfrage | Verhalten |
|---|---|
| `/_next/static/*`, `/icons/*`, `/offline.html` (eigene Origin, GET) | Cache-first; beim ersten Abruf gespeichert |
| Seitenaufruf (`navigate`) | immer ans Netz, **nie** gespeichert; ohne Netz `/offline.html` |
| alles andere (RSC, `/auth`, `/api`, Dokumente, Fragen, fremde Origins, Schreibzugriffe) | kein `respondWith` – Browser-Standard, nichts gespeichert |

Bei der Installation wird nur `/offline.html` vorab geladen. Eine beim Build erzeugte Precache-Liste (ursprünglich `scripts/sw-manifest.mjs` im F11-Design) entfällt: Die Demo braucht ohnehin Netz, und ohne Build-Schritt gibt es nichts, das beim Next-Update brechen kann. `/sw.js` wird mit `Cache-Control: no-cache` ausgeliefert, damit Korrekturen sofort ankommen; ein neuer Cache-Name räumt alte Versionen beim Aktivieren ab.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Serwist / next-pwa | Build-Integration für Webpack; Standardregeln cachen Seiten – hätte man mühsam abschalten müssen |
| Gar kein Service Worker | Keine Offline-Seite; Chrome bietet die Installation trotzdem an, aber AC3 wäre nicht erfüllt |
| Precache-Liste aus dem Build | Mehr bewegliche Teile ohne Nutzen für eine Online-Demo |

## Konsequenzen
+ Nachweisbar: Nach einem typischen Ablauf liegen nur Build-Dateien, Icons und die Offline-Seite im Cache (`e2e/pwa.spec.ts`); die Allowlist ist als Tabellentest mit der echten `sw.js` geprüft (`src/app/__tests__/service-worker.test.ts`).
+ Rollenwechsel und Abmelden hinterlassen keine Fachdaten im Cache.
− Kein Offline-Lesen der Akte – bewusst (Datenschutz vor Komfort).
