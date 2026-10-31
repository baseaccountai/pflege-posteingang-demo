# ADR 0012: Agenten-Token per Token Exchange in Zitadel

Status: angenommen · Datum: 31.10.2026 · Spike zu F08 Aufgabe 1 (`F08-AC1`, `F08-AC2a`)

## Kontext
Der Agent (F08) handelt im Auftrag der angemeldeten Pflegekraft. Er soll dafür ein **eigenes** Token bekommen, nicht das Token der Pflegekraft: An ihm muss erkennbar sein, *wer* handelt (der Agent) und *für wen* (die Pflegekraft), damit RLS und Protokoll beides unterscheiden. Vorgesehen waren zwei Wege:

- **a) Token Exchange** (RFC 8693) beim Identity Provider: Zitadel tauscht das Token der Pflegekraft gegen ein Agenten-Token mit `act`-Claim.
- **b) Rückfall:** Die API prüft das Nutzer-Token und signiert selbst ein Agenten-JWT (`AGENT_TOKEN_MODE=self_signed`).

Bis zum Spike stand Token Exchange nicht im Discovery-Dokument der Instanz (`grant_types_supported`), und die Doku beschrieb ihn als Beta-Funktion hinter einem Feature-Schalter.

## Spike (31.10.2026, Zitadel Cloud, Instanz `rbni7a`)
Skript `apps/api/scripts/agent_token_spike.py` (`setup`, dann `exchange` mit Login als `pflege-wb1`).

| Schritt | Befund |
|---|---|
| Feature-Schalter | In der Konsole nicht mehr vorhanden; seit Zitadel v4.11 wird Token Exchange je App über den Grant-Typ freigeschaltet. Im Discovery steht er weiterhin **nicht**. |
| Instanz | „Allow Impersonation“ in den Sicherheitseinstellungen (Instanz-Admin, Konsole) |
| Agent | Service-User `pp-agent` (`sub` 397592785986842667), JWT-Access-Tokens, Client Credentials, Organisationsrolle `ORG_END_USER_IMPERSONATOR` (darf nur für Nutzer ohne Admin-Mitgliedschaft handeln) |
| Tausch-Client | Eigene vertrauliche App `pflege-posteingang-agent` (Basic Auth). Zitadel lehnt eine App nur mit Token-Exchange-Grant ab (`PROJECT-1n8df`, Antworttyp `code` verlangt den Code-Grant); sie hat deshalb Code + Token Exchange, einzige Redirect-URI `localhost`. Die Web-App bekommt den Grant **nicht**. |
| Agenten-Token (Client Credentials) | HTTP 200; `aud` = Projekt, keine Rollen |
| Tausch | HTTP 200, `issued_token_type` = `urn:ietf:params:oauth:token-type:jwt`, Signatur per JWKS gültig |

### Tatsächlich ausgestellte Claims (getauschtes Token)

| Claim | Wert | Prüfung in der API (`F08-AC3`) |
|---|---|---|
| `iss` | `https://pflege-posteingang-demo-rbni7a.eu1.zitadel.cloud` | = `OIDC_ISSUER` |
| `aud` | Projekt `396809504747974809` und die Client-IDs der Projekt-Apps (`396809508069835626` Web, `397593021354416029` Agent) | enthält `OIDC_AUDIENCE` |
| `sub` | `396838961344968028` – die Pflegekraft, gleich wie im Nutzer-Token | = Nutzer der Sitzung |
| `act` | `{"iss": "<Issuer>", "sub": "397592785986842667"}` | Pflicht; `act.sub` = `AGENT_ID`, `act.iss` = Issuer |
| Rollen | `urn:zitadel:iam:org:project:roles` = `{"nurse_wb1": {…}}` und `urn:zitadel:iam:org:project:396809504747974809:roles` – unverändert aus dem Nutzer-Token | Wohnbereiche wie in F01 |
| `exp − iat` | **3600 s** | siehe Entscheidung |
| weitere | `client_id`, `jti`, `nbf` | – |

Das Nutzer-Token hat dieselben Claims **ohne** `act`; das Agenten-Token aus Client Credentials hat `sub` = Agent und keine Rollen.

## Entscheidung
1. **Weg a: Token Exchange in Zitadel** ist der Weg der öffentlichen Demo (`AGENT_TOKEN_MODE=exchange`). Der Rückfall b bleibt als Modus erhalten und getestet (lokaler Betrieb, andere Identity Provider).
2. **Laufzeit in der API:** Zitadel stellt Access-Tokens mindestens 1 h aus (die Konsole erlaubt nur ganze Stunden; die Admin-API wäre kürzer, gälte aber für alle Tokens der Instanz und bräuchte Instanz-Admin-Rechte für ein Skript). Die API nimmt ein Agenten-Token deshalb nur an, solange `now − iat ≤ AGENT_TOKEN_MAX_SECONDS` (300 s), hält es nur im Speicher und verwirft es nach dem Auftrag (`F08-AC1`, geändert am 31.10.2026 mit Freigabe des Bewerbers).
3. **Kein Token mit `act` als Nutzer-Token:** Das getauschte Token besteht alle Prüfungen eines Nutzer-Tokens (gleicher Aussteller, Zielgruppe, `sub`, Rollen). Die normale Token-Prüfung aus F01 lehnt deshalb jedes Token mit `act` ab; nur der `AgentTokenVerifier` nimmt es an und erzeugt `actor_type = agent`. Sonst könnte ein Agenten-Token alles, was die Pflegekraft kann, ohne die Grenzen des Agenten.
4. **Nur der Tausch-Client hat den Grant.** Konfiguration: `AGENT_CLIENT_ID`/`AGENT_CLIENT_SECRET` (Service-User), `AGENT_EXCHANGE_CLIENT_ID`/`AGENT_EXCHANGE_CLIENT_SECRET` (Tausch-App), `AGENT_ID` = `sub` des Service-Users. Alles nur im Backend.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Rückfall b (API signiert selbst) | Funktioniert ohne Identity Provider, aber der Tausch ist dann nicht vom Identity Provider bestätigt und nicht in dessen Protokoll („User impersonated“); die API wäre zugleich Aussteller und Prüfer. Bleibt Rückfall. |
| Instanzweit 5 min per Admin-API | Kürzere Tokens auch beim Identity Provider, aber für alle Tokens der Instanz und nur mit vorübergehenden Instanz-Admin-Rechten für ein Skript. |
| Nutzer-Token direkt an den Agenten | Agent und Mensch wären in RLS und Protokoll nicht zu unterscheiden (widerspricht `F08-AC3`, `F12`). |

## Konsequenzen
+ Der Identity Provider bestätigt jede Delegation und protokolliert sie; `act` ist ein Standard-Claim (RFC 8693), keine Eigenerfindung.
+ Rollen und Wohnbereiche kommen unverändert aus dem Nutzer-Token: Der Agent kann nie mehr als die Pflegekraft.
− **Restrisiko Laufzeit:** Technisch gilt das Token beim Identity Provider 1 h. Die 5-Minuten-Grenze erzwingt nur unsere API; da das Token das Backend nie verlässt (`F08-AC3`) und nach dem Auftrag verworfen wird, bleibt es eine Vorsichtsmaßnahme gegen Wiederverwendung im Backend selbst.
− **Instanzweite Einstellung:** „Allow Impersonation“ gilt für die ganze Instanz; begrenzt wird es durch die Rolle `ORG_END_USER_IMPERSONATOR` (nur ein Service-User, nur Endnutzer) und den Grant an nur einer App.
− **Bekannte Lücke im Tausch-Endpunkt:** CVE-2026-56668 (GHSA-vrh8-c9cm-wh8v, CVSS 8.1, behoben in Zitadel v4.15.3, veröffentlicht 14.09.2026): Zitadel prüfte nicht, ob das eingetauschte Token zum anfragenden Client gehört, und erzwang angefragte Scopes nicht. Zitadel Cloud sollte gepatcht sein (Version nicht von außen geprüft). Unsere API vertraut dem getauschten Token deshalb nicht allein: Sie prüft `sub` gegen die Sitzung, `act.sub` gegen `AGENT_ID` und die Zielgruppe selbst.
− Die Einrichtung (Service-User, Rolle, Tausch-App) steht noch im Spike-Skript; sie wandert mit F08 in `infra/zitadel/setup.py`. „Allow Impersonation“ bleibt ein Handgriff in der Konsole.
