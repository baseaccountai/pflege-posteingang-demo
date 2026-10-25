# ADR 0004: Next.js als Backend-for-Frontend

Status: angenommen · Datum: 23.10.2026

## Kontext
Die Web-App soll mobil als PWA laufen und OIDC-Login nutzen. Access- und Refresh-Tokens im Browser (z. B. `localStorage`) sind durch XSS angreifbar.

## Entscheidung
**Next.js (App Router)** ist Oberfläche **und** Backend-for-Frontend: Der OIDC-Login (Authorization Code + PKCE) läuft serverseitig, der Browser erhält nur ein **HttpOnly-Session-Cookie**. Next.js leitet Anfragen mit dem Token serverseitig an FastAPI weiter und enthält keine Fachlogik. Gestaltung mit Tailwind und shadcn/ui; Hosting auf Vercel.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| SPA mit Tokens im Browser | Tokens per XSS auslesbar |
| Login direkt in FastAPI | Session-Handling und Oberfläche getrennt; mehr Aufwand für PWA-Auslieferung |

## Konsequenzen
+ Tokens nie im Browser; aktuelle Best Practice (OAuth 2.0 for Browser-Based Apps, BFF-Muster).
− Eine zusätzliche Server-Hop pro Anfrage.
