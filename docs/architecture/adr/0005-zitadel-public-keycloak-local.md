# ADR 0005: Zitadel öffentlich, Keycloak lokal

Status: angenommen · Datum: 23.10.2026

## Kontext
Echter OIDC-Login mit drei Demo-Rollen (Pflegekraft WB1, Pflegekraft WB2, PDL) ist gefordert; für Agent-Aktionen soll per **Token Exchange (RFC 8693)** ein eingeschränktes Agenten-Token entstehen. Öffentlich ohne eigenen Server, lokal komplett offline.

## Entscheidung
Öffentlich **Zitadel Cloud** (europäischer Anbieter), lokal **Keycloak** in Docker mit vorkonfiguriertem Realm. Demo-Nutzer werden als Code gepflegt (`infra/zitadel/` Setup-Skript, `infra/keycloak/` Realm-Import) mit gleichen Nutzern, Rollen und Claims. Die Token-Exchange-Unterstützung wird im Spike in Phase 2 geprüft.

## Alternativen
| Alternative | Warum nicht |
|---|---|
| Supabase Auth | belegt keinen eigenständigen OIDC-IdP; Token Exchange (RFC 8693) nach Stand der Recherche nicht unterstützt – Annahme, zu prüfen |
| Auth0 / Entra ID | nicht europäisch, Kosten |
| Keycloak auch öffentlich | eigener Server mit RAM-Bedarf, Budget |

## Konsequenzen
+ Standardkonformes OIDC, IdP per Konfiguration austauschbar.
− Zwei IdPs pflegen; Rückfall bei fehlendem Token Exchange: Backend stellt ein selbst signiertes, eingeschränktes Agenten-JWT aus.
