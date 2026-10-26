# F01 – Login & Rollen (OIDC), Rollenwechsel: Anforderungen

Status: freigegeben 25.10.2026 · Stufe: 1 · Bildschirme: 1 (Rollenwechsel), 8 (Kein Zugriff) · Datenmodell: [../datenmodell.md](../datenmodell.md)

## Einführung

Besucher melden sich mit echten OIDC-Logins als eine von drei Demo-Rollen an. Wohnbereichs-Rechte werden in der Datenbank (RLS) erzwungen. **Tokens gelangen nie in den Browser** – auch nicht verschlüsselt: Das Cookie enthält nur eine zufällige Sitzungs-ID, die Tokens liegen serverseitig. Grundlage: Design 5.2, 5.3, 10; ADR 0004.

**Umfang Stufe 1:** öffentlicher IdP Zitadel. Lokaler IdP (Keycloak) folgt in Phase 8 aus denselben Nutzerdefinitionen; automatische Tests nutzen einen Test-OIDC-Server. Token Exchange wird in F08 (Stufe 2) geklärt.

## User Stories

- **US-1:** Als Besucher möchte ich mit einem Klick eine Demo-Rolle wählen und mich regulär beim Identity Provider anmelden, damit ich die Rechte-Trennung selbst ausprobieren kann.
- **US-2:** Als Pflegekraft WB1 möchte ich nur Bewohner und Dokumente meines Wohnbereichs sehen.
- **US-3:** Als PDL möchte ich alle Wohnbereiche sehen.
- **US-4:** Als Prüfer der Demo möchte ich sehen, dass ein fremder Wohnbereich auch per direkter URL oder direktem API-Aufruf nicht erreichbar ist.

## Akzeptanzkriterien (EARS)

| ID | Kriterium |
|---|---|
| F01-AC1 | WENN ein Besucher auf der Startseite den Knopf einer Rolle wählt, DANN soll das System eine bestehende Sitzung beenden und einen OIDC-Login (Authorization Code mit PKCE S256, `state`, `nonce`, `prompt=login`, `login_hint` der Rolle) auf der Login-Seite des Identity Providers starten. |
| F01-AC2 | Das System soll neben jedem Rollenknopf Benutzername und Passwort des Demo-Kontos mit einer Kopier-Schaltfläche anzeigen. |
| F01-AC3 | WENN der Identity Provider mit gültigem Code zurückleitet, DANN soll das System die Tokens serverseitig einlösen, sie verschlüsselt in der Sitzungstabelle speichern und dem Browser nur ein Cookie `__Host-pp_sid` mit einer zufälligen Sitzungs-ID (≥ 256 Bit) setzen (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`). |
| F01-AC4 | Das System soll Access-, Refresh- und ID-Token in keiner Form an den Browser ausliefern (HTML, JavaScript, Cookies, Storage, Antworten des BFF). |
| F01-AC5 | FALLS `state`, `nonce` oder PKCE-Prüfung beim Rücksprung fehlschlägt oder der Rücksprung ein zweites Mal verwendet wird, DANN soll das System keine Sitzung anlegen und eine Fehlermeldung mit Link zur Startseite zeigen. |
| F01-AC6 | WENN die API eine Anfrage erhält, DANN soll sie das Access-Token über JWKS prüfen (Signatur, `iss`, `aud`, `exp`, `nbf`, Algorithmus aus fester Liste) und bei Fehler mit 401 ohne Fachdaten antworten. |
| F01-AC7 | Die API soll aus den Rollen-Claims `app_role` und `ward_ids` ableiten: `nurse_wb1` → `nurse`/`[wb1]`, `nurse_wb2` → `nurse`/`[wb2]`, `pdl` → `pdl`/`[wb1, wb2]`; ohne bekannte Rolle → 403. |
| F01-AC8 | Die API soll Fach-Routen nur mit gültigem BFF-Nachweis (kurzlebige, signierte Zusicherung mit Sitzungs-ID) beantworten; ein Aufruf mit gültigem Nutzer-Token, aber ohne gültigen BFF-Nachweis, wird mit 401 abgelehnt. |
| F01-AC9 | Die API soll auf die Datenbank ausschließlich als Rolle `authenticated` mit den abgeleiteten Claims zugreifen; der Service-Key wird im Anfragepfad nicht verwendet. |
| F01-AC10 | WENN eine Pflegekraft WB2 Bewohner oder Dokumente abfragt, DANN soll die Datenbank keine Zeile aus WB1 liefern – auch bei Abfrage ohne `where`-Filter, nach einem Fehler/Rollback einer vorherigen WB1-Transaktion auf derselben Verbindung und bei parallelen Anfragen beider Rollen. |
| F01-AC11 | FALLS keine Claims gesetzt sind, DANN soll die Datenbank keine Zeilen liefern und Schreibzugriffe ablehnen. |
| F01-AC12 | WENN eine Pflegekraft die Akte eines Bewohners aus einem fremden Wohnbereich oder eine nicht existierende Bewohner-ID aufruft, DANN soll das System dieselbe Seite „Nicht gefunden oder kein Zugriff“ (Bildschirm 8) zeigen und nicht verraten, ob der Bewohner existiert. |
| F01-AC13 | WENN ein Nutzer die Rolle wechselt oder sich abmeldet, DANN soll das System die Tokens serverseitig beim IdP widerrufen (Revocation-Endpunkt), die Sitzung löschen und das Cookie löschen; beim **Abmelden** leitet es den Browser ohne Token-Parameter zum IdP-Logout (`end_session` mit `client_id` und `post_logout_redirect_uri`), beim **Rollenwechsel** direkt zum Login der neuen Rolle (`prompt=login` erzwingt neue Anmeldedaten; Zitadel zeigt beim `end_session` eine Seite mit Klick, Spike S2); danach zeigt keine Seite, Antwort oder Liste mehr Daten der vorherigen Rolle (auch nicht über Zurück-Taste, Router-Cache oder eine verspätet eintreffende Antwort). |
| F01-AC14 | Das System soll Seiten und BFF-Antworten mit Nutzerdaten mit `Cache-Control: no-store` ausliefern. |
| F01-AC15 | WENN eine schreibende BFF-Anfrage (POST/PUT/PATCH/DELETE) einen fehlenden oder fremden `Origin`-Header hat, DANN soll das System sie mit 403 ablehnen (CSRF-Schutz); fachliche Änderungen erfolgen nie per GET. |
| F01-AC16 | Die Demo-Nutzer, Rollen und Claims sollen als Code angelegt werden: gemeinsame Definition `infra/demo-users.json`, Zitadel per idempotentem Setup-Skript `infra/zitadel/setup.py` (Keycloak-Realm aus derselben Datei in Phase 8). |
| F01-AC17 | Die Demo-Konten sollen keine Admin-Rechte im Identity Provider haben. |
| F01-AC18 | WENN ein Demo-Nutzer sein Passwort ändert, DANN soll das System es innerhalb von 15 Minuten auf das veröffentlichte Demo-Passwort zurücksetzen (sofern der IdP die Änderung nicht ohnehin verhindert – Ergebnis aus Spike S4). |
| F01-AC19 | WO der Identity Provider per Konfiguration gewechselt wird (`OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_AUDIENCE`, `OIDC_SCOPES`, `OIDC_ROLES_CLAIM`), soll das System ohne Codeänderung funktionieren – nachgewiesen mit Zitadel und dem Test-OIDC-Server. |
| F01-AC20 | Die Kopfzeile soll die angemeldete Rolle anzeigen (z. B. „Pflegekraft WB1“) und einen Abmelde-Knopf bieten. |
| F01-AC21 | WENN eine Sitzung abläuft (max. 8 h), widerrufen ist oder der Token-Refresh fehlschlägt, DANN soll das System zur Startseite mit dem Hinweis „Sitzung abgelaufen – bitte Rolle wählen“ leiten. |

## Spike (erste Aufgabe, Ergebnis als ADR 0007)

| Frage | Erfolg, wenn |
|---|---|
| S1: Datenbankzugriff „im Namen des Nutzers“ über `set local role authenticated` + `request.jwt.claims` über den Supabase-Pooler (Transaktionsmodus, psycopg ohne Prepared Statements) | F01-AC10 und F01-AC11 grün gegen lokales und Cloud-Supabase |
| S2: Zitadel-Client: Web-App mit Code + PKCE und Client-Secret (Basic); JWT-Access-Token mit Projekt-Rollen und Projekt-`aud` über die Scopes | F01-AC6/AC7 grün mit echtem Zitadel-Token; sonst Rückfall auf öffentlichen PKCE-Client |
| S3: BFF-Datenbankzugriff von Vercel auf `bff.sessions` über den Pooler | Sitzung anlegen/lesen/widerrufen von einer Vercel-Funktion |
| S4: Kann Zitadel Passwortänderungen der Demo-Nutzer verhindern (Self-Service, Konsole)? | Ergebnis dokumentiert; sonst AC18 per Workflow |

## Nicht im Umfang

Registrierung, Passwort-Reset durch Nutzer, eigene Nutzerverwaltung, Keycloak (Phase 8), Agenten-Token und Token Exchange (F08), Protokoll (F12).
