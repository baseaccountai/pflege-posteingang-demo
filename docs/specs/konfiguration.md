# Konfiguration (alle Umgebungsvariablen)

Stand: 28.10.2026 · Einzige Übersicht; `.env.example` listet dieselben Namen ohne Werte. **Geheim** = nur in `.env` bzw. Secret-Stores, nie im Repo, nie im Chat.

| Variable | Dienst | Pflicht | Standard | Geheim | Zweck |
|---|---|---|---|---|---|
| `LLM_PROVIDER` | API | ja | `mistral` | nein | `mistral` \| `ollama` \| `fake` (nur Tests/E2E: regelbasierte Attrappe) |
| `OCR_PROVIDER` | API | ja | `mistral` | nein | `mistral` \| `docling` \| `fake` (nur Tests/E2E: feste Texte statt OCR) |
| `MISTRAL_API_KEY` | API, Seed-Skript | bei `mistral` | – | **ja** | Mistral-Zugang |
| `MISTRAL_CHAT_MODEL` | API | bei `mistral` | `mistral-small-latest` | nein | Feldvorschläge, Antworten |
| `MISTRAL_OCR_MODEL` | API | bei `mistral` | aus ADR 0003 | nein | OCR |
| `MISTRAL_EMBED_MODEL` | API | bei `mistral` | `mistral-embed` | nein | Embeddings (1024) |
| `GUARD_MODEL` | API | nein | `ministral-8b-latest` | nein | Injection-Klassifikator (F07, Stufe 2) |
| `AGENT_TOKEN_MODE` | API | Stufe 2 | `exchange` | nein | `exchange` (RFC 8693 beim IdP) \| `self_signed` (Rückfall), F08 |
| `AGENT_ID` | API | Stufe 2 | – | nein | erwartetes `act.sub` (Service-User des Agenten), F08 |
| `AGENT_CLIENT_ID`, `AGENT_CLIENT_SECRET` | API | bei `exchange` | – | **ja** (Secret) | Zugang des Agenten-Service-Users zum Token-Endpunkt, F08 |
| `AGENT_SIGNING_KEY` | API | bei `self_signed` | – | **ja** | ES256-Schlüssel für selbst ausgestellte Agenten-Tokens, F08 |
| `AGENT_TOKEN_MAX_SECONDS` | API | nein | `300` | nein | längste angenommene Laufzeit eines Agenten-Tokens, F08 |
| `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL` | API | bei `ollama` (Phase 8) | `http://localhost:11434`, `qwen3:8b`, `bge-m3` | nein | lokales LLM; das Embedding-Modell muss 1024 Dimensionen liefern (sonst `EmbeddingUnavailable`) |
| `DOCLING_BASE_URL` | API | bei `docling` (Phase 8) | – | nein | lokale OCR |
| `RAG_MIN_SIMILARITY` | API | nein | `0.72` | nein | Treffer-Schwelle (F05), kalibriert mit mistral-embed am 28.10.2026; ein lokales Modell braucht eigene Kalibrierung |
| `OIDC_ISSUER` | Web, API | ja | – | nein | IdP-Adresse |
| `OIDC_CLIENT_ID` | Web | ja | – | nein | OIDC-Client |
| `OIDC_CLIENT_SECRET` | Web | bei Basic (Spike S2) | – | **ja** | Client-Authentifizierung |
| `OIDC_AUDIENCE` | API | ja | – | nein | erwartetes `aud` |
| `OIDC_SCOPES` | Web | ja | siehe F01-Design | nein | angeforderte Scopes |
| `OIDC_ROLES_CLAIM` | Web, API | ja | `urn:zitadel:iam:org:project:roles` | nein | Claim mit Rollen |
| `APP_ORIGIN` | Web | ja | – | nein | erlaubter `Origin` (CSRF), Redirect-Basis |
| `SESSION_ENC_KEY` | Web | ja | – | **ja** | AES-256-GCM für Tokens in `bff.sessions`; 32 Byte, Base64 (`openssl rand -base64 32`) |
| `BFF_DATABASE_URL` | Web | ja | – | **ja** | Rolle `bff_session` über Pooler |
| `BFF_API_SECRET` | Web, API | ja | – | **ja** | Signatur des BFF-Nachweises |
| `API_BASE_URL` | Web | ja | `http://localhost:8000` | nein | API-Adresse |
| `API_BASE_URL` (Repository-Variable) | Keep-alive-Workflow | ja (nur GitHub, `vars`) | – | nein | öffentliche API-Adresse für `GET /health/ready` (F10-AC9) |
| `DATABASE_URL` | API | ja | – | **ja** | Rolle `api_gateway` über Pooler (Transaktionsmodus) |
| `SUPABASE_URL` | Skripte | nein | – | nein | Projekt-URL |
| `SUPABASE_PUBLISHABLE_KEY` | – | nein | – | nein (aber nicht veröffentlichen) | derzeit ungenutzt (kein Browserzugriff auf Supabase) |
| `SUPABASE_SECRET_KEY` | – | nein | – | **ja** | derzeit ungenutzt; nie im Anfragepfad |
| `SUPABASE_DB_ADMIN_URL` | Reset- und Deploy-Workflow, Rollen-Skript | ja (GitHub-Secret; lokal in `.env`) | – | **ja** | Reset und Seed (F10, `nightly-reset.yml`); Migrationen im Deploy (`supabase db push --db-url`, F11); Session-Pooler, Port 5432. Darum braucht der Deploy kein `SUPABASE_ACCESS_TOKEN` |
| `ZITADEL_ADMIN_PAT` | Setup-Skript, Passwort-Workflow | für Setup | – | **ja** | Management-API |
| `ZITADEL_PROJECT_ID` | Setup-Skript, Passwort-Workflow | für Setup | – | nein | Zitadel-Projekt (= `OIDC_AUDIENCE`), schreibt das Setup-Skript |
| `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | Deploy-Workflow | ja (nur GitHub) | – | **ja** (IDs: nein) | Web-Deployment (`deploy.yml`, nur nach grüner CI auf `main`); Token unter vercel.com → Account Settings → Tokens, IDs unter Settings → General |
| `VERCEL_API_PROJECT_ID` | Deploy-Workflow | ja (nur GitHub) | – | nein | API-Deployment (zweites Vercel-Projekt, ADR 0011; ersetzt `KOYEB_*`) |
| `NEXT_PUBLIC_REPO_URL` | Web | ja | – | nein | Repo-Links der Landkarte (F09) |

Kontingente stehen **nicht** in Variablen, sondern in der Tabelle `quota_limits` (F10), damit Aufrufer sie nicht beeinflussen.
