# ADR 0009: Login-Sitzung serverseitig in Postgres

Status: angenommen · Datum: 25.10.2026 (Entscheidung des Bewerbers nach Codex-Review der Specs)

## Kontext
ADR 0004 verlangt, dass Access-/Refresh-Tokens nie in den Browser gelangen. Ein verschlüsseltes Session-Cookie (JWE) hätte die Tokens zwar unlesbar, aber doch im Browser gespeichert; zudem drohte die 4-KB-Cookiegrenze, und ein Logout könnte ein kopiertes Cookie nicht entwerten.

## Entscheidung
Das Cookie `__Host-pp_sid` enthält nur eine zufällige Sitzungs-ID. Die Tokens liegen AES-256-GCM-verschlüsselt in `bff.sessions` (gespeichert wird nur der SHA-256-Hash der ID). Zugriff ausschließlich über die Datenbankrolle `bff_session`; das Schema ist nicht über die Supabase-REST-API erreichbar.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Verschlüsseltes Cookie | Tokens (verschlüsselt) im Browser, Größenlimit, kein serverseitiger Widerruf |
| Redis/Upstash | zusätzlicher Dienst und Anbieter |

## Konsequenzen
+ „Tokens nie im Browser“ wörtlich erfüllt; Logout/Rollenwechsel widerruft sofort.
− Next.js braucht eine eingeschränkte Datenbankverbindung (Spike S3 in F01); ca. 3 h Mehraufwand.
