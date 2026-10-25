# F01 – Login & Rollen (OIDC), Rollenwechsel: Anforderungen

Status: Entwurf · Stufe: 1 · Bildschirme: 1 (Rollenwechsel), 8 (Kein Zugriff) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Besucher melden sich mit echten OIDC-Logins als eine von drei Demo-Rollen an. Wohnbereichs-Rechte werden in der Datenbank (RLS) erzwungen. Tokens gelangen nie in den Browser. Grundlage: Design 5.2, 5.3, 10 (Risiko Zitadel ↔ Supabase-RLS).

## User Stories

- **US-1:** Als Besucher möchte ich mit einem Klick eine Demo-Rolle wählen und mich regulär beim Identity Provider anmelden, damit ich die Rechte-Trennung selbst ausprobieren kann.
- **US-2:** Als Pflegekraft WB1 möchte ich nur Bewohner und Dokumente meines Wohnbereichs sehen.
- **US-3:** Als PDL möchte ich alle Wohnbereiche sehen.
- **US-4:** Als Prüfer der Demo möchte ich sehen, dass ein fremder Wohnbereich auch per direkter URL nicht erreichbar ist.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F01-AC1 | WENN ein Besucher auf der Startseite den Knopf einer Rolle wählt, DANN soll das System eine bestehende Sitzung beenden und einen OIDC-Login (Authorization Code + PKCE mit S256, `state`, `nonce`) auf der Login-Seite des Identity Providers starten. |
| F01-AC2 | Das System soll neben jedem Rollenknopf Benutzername und Passwort des Demo-Kontos mit einer Kopier-Schaltfläche anzeigen. |
| F01-AC3 | WENN der Identity Provider mit gültigem Code zurückleitet, DANN soll das System die Tokens serverseitig einlösen und dem Browser nur ein Session-Cookie mit `HttpOnly`, `Secure`, `SameSite=Lax` und Präfix `__Host-` setzen. |
| F01-AC4 | Das System soll Access-, Refresh- und ID-Token weder in HTML, JavaScript-Bundles, `localStorage`/`sessionStorage` noch in für JavaScript lesbaren Cookies ausliefern. |
| F01-AC5 | FALLS `state`, `nonce` oder PKCE-Prüfung beim Rücksprung fehlschlägt, DANN soll das System keine Sitzung anlegen und eine Fehlermeldung mit Link zur Startseite zeigen. |
| F01-AC6 | WENN die API eine Anfrage erhält, DANN soll sie das Access-Token über JWKS prüfen (Signatur, `iss`, `aud`, `exp`, `nbf`, Algorithmus aus fester Liste) und bei Fehler mit 401 ohne Fachdaten antworten. |
| F01-AC7 | Die API soll aus den Rollen-Claims des Tokens `app_role` und `ward_ids` ableiten: `nurse_wb1` → `nurse`/`[wb1]`, `nurse_wb2` → `nurse`/`[wb2]`, `pdl` → `pdl`/`[wb1, wb2]`; ein Token ohne bekannte Rolle erhält 403. |
| F01-AC8 | Die API soll auf die Datenbank ausschließlich als Rolle `authenticated` mit den abgeleiteten Claims zugreifen, sodass Row Level Security greift; der Service-Key wird im Anfragepfad nicht verwendet. |
| F01-AC9 | WENN eine Pflegekraft WB2 Bewohner oder Dokumente abfragt, DANN soll die Datenbank keine Zeile aus WB1 liefern – auch bei direkter SQL-Abfrage ohne `where`-Filter. |
| F01-AC10 | WENN eine Pflegekraft die Akte eines Bewohners aus einem fremden Wohnbereich oder eine nicht existierende Bewohner-ID aufruft, DANN soll das System dieselbe Seite „Nicht gefunden oder kein Zugriff“ (Bildschirm 8) zeigen und nicht verraten, ob der Bewohner existiert. |
| F01-AC11 | WENN ein Nutzer die Rolle wechselt, DANN soll das System das Session-Cookie löschen, den Logout beim Identity Provider auslösen und danach keine Seite, Antwort oder Liste der vorherigen Rolle mehr anzeigen (auch nicht über Zurück-Taste oder Router-Cache). |
| F01-AC12 | Das System soll Seiten mit Nutzerdaten mit `Cache-Control: no-store` ausliefern. |
| F01-AC13 | Die Demo-Nutzer, Rollen und Claims sollen als Code angelegt werden: Zitadel per idempotentem Setup-Skript in `infra/zitadel/`, Keycloak per Realm-Import in `infra/keycloak/`, mit gleichen Benutzernamen, Rollen und Claim-Namen. |
| F01-AC14 | Die Demo-Konten sollen keine Admin-Rechte im Identity Provider haben. |
| F01-AC15 | WO der Identity Provider per Konfiguration gewechselt wird (`OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_AUDIENCE`, `OIDC_ROLES_CLAIM`), soll das System ohne Codeänderung mit Zitadel und Keycloak funktionieren. |
| F01-AC16 | Die Kopfzeile soll die angemeldete Rolle anzeigen (z. B. „Pflegekraft WB1“) und einen Abmelde-Knopf bieten. |
| F01-AC17 | WENN eine Sitzung abläuft (max. 8 h) oder der Refresh fehlschlägt, DANN soll das System zur Startseite mit dem Hinweis „Sitzung abgelaufen – bitte Rolle wählen“ leiten. |

## Spike (erste Aufgabe, Ergebnis als ADR 0007)

| Frage | Erfolg, wenn |
|---|---|
| S1: Funktioniert der Datenbankzugriff „im Namen des Nutzers“ über `set local role authenticated` + `request.jwt.claims` über den Supabase-Pooler? | RLS-Test F01-AC9 grün gegen Cloud-Supabase und lokales Supabase |
| S2: Liefert Zitadel ein JWT-Access-Token mit Projekt-Rollen und passendem `aud`? | Token-Prüfung F01-AC6 grün mit echtem Zitadel-Token |
| S3: Ist Token Exchange (RFC 8693) in Zitadel (Feature-Flag) und Keycloak verfügbar? | Ergebnis dokumentiert; Umsetzung erst in F08 |

## Nicht im Umfang

Registrierung, Passwort-Reset, eigene Nutzerverwaltung, Agenten-Token (F08), Protokoll (F12).
