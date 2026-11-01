.PHONY: setup test test-api test-web test-db db-start db-stop db-reset reset e2e lint up down samples sample-record seed-chunks rag-probe security-report up-test smoke db-local-roles project-description screens keycloak-realm reindex up-local smoke-local

SUPABASE := pnpm dlx supabase@2.122.0

# One-time install of all dependencies (incl. Playwright browser)
setup:
	cd apps/api && uv sync --frozen
	cd apps/web && pnpm install --frozen-lockfile && pnpm exec playwright install chromium

test: test-api test-web

test-api:
	cd apps/api && uv run pytest -v

test-web:
	cd apps/web && pnpm test

# Database tests need the local Supabase stack (make db-start)
test-db:
	cd apps/api && uv run pytest -m db -v
	cd apps/web && pnpm test:db

db-start:
	$(SUPABASE) start

db-stop:
	$(SUPABASE) stop

# Re-create the local database from supabase/migrations
db-reset:
	$(SUPABASE) db reset

# Nightly reset of the demo data against the local Supabase (F10; same code as the Action)
reset:
	cd apps/api && uv run python -m scripts.reset_demo --local

# Needs the local Supabase stack (make db-start), Docker (test OIDC server) and uv (API)
e2e:
	cd apps/web && pnpm e2e

# Regenerates the sample documents in samples/ (reproducible, commit the result)
samples:
	cd apps/api && PYTHONPATH=../.. uv run python -m samples.generate ../../samples
	# F07-AC14: the documents offered for download in the inbox (a test checks they match)
	cp samples/arztbrief_muster-bauer.pdf samples/arztbrief_muster-bauer_foto.jpg \
	   samples/medikationsplan_muster-bauer.pdf samples/angriff_versteckt_probe.pdf \
	   samples/angriff_hinweis_beispiel.pdf apps/web/public/samples/

# Precomputed seed chunks with real Mistral embeddings (F10-AC6); run by the applicant,
# reads MISTRAL_API_KEY from .env and never prints it
seed-chunks:
	cd apps/api && PYTHONPATH=../.. uv run python -m scripts.build_seed_chunks ../../.env

# Real test of questions (F05 Task 8): resets the LOCAL Supabase, asks Mistral 6 questions
rag-probe:
	cd apps/api && PYTHONPATH=../.. uv run python -m scripts.rag_probe ../../.env

# F13-AC5: corpus against rules + the real checker model; writes docs/security/reports/
# (applicant, own terminal; reads only MISTRAL_API_KEY from .env; resets the LOCAL database)
security-report:
	cd apps/api && PYTHONPATH=../.. uv run python -m scripts.security_report ../../.env

# Static sample record for /muster from the seed (F10-AC14); resets the local Supabase first
sample-record:
	cd apps/api && uv run python -m scripts.build_sample_record

# Project description (phase 9): copies docs/projektbeschreibung.md and its pictures into the web app
project-description:
	cd apps/web && node scripts/copy-project-description.mjs

# Screenshots for the project description: LOCAL database back to the seed, e2e stack with
# the fake models, then make project-description
screens:
	cd apps/api && env -u SUPABASE_DB_ADMIN_URL uv run python -m scripts.reset_demo --local
	cd apps/web && pnpm build && SCREENS=1 pnpm exec playwright test e2e/screens.spec.ts --project=desktop --project=mobile
	$(MAKE) project-description

lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check .
	cd apps/web && pnpm lint

# Local stack (F11-AC5): Supabase via CLI, then web + api with plain Docker (host network)
up: db-start db-local-roles
	infra/local-stack.sh up

# Same, plus the test OIDC server and fake providers - no account or key needed
up-test: db-start db-local-roles
	infra/local-stack.sh up-test

# Index all approved documents again with the configured embedding model - local database
# only (F05-AC13, F11-AC19); `make up-local` calls it after the seed
reindex:
	cd apps/api && LLM_PROVIDER=ollama uv run python -m scripts.reindex

# Keycloak realm of the fully local mode from infra/demo-users.json (F11-AC15; commit it)
keycloak-realm:
	python3 infra/keycloak/build_realm.py

# Everything on this machine (F11-AC13): Keycloak, Docling, Ollama (native), no .env.
# Resets the LOCAL demo data to the seed and indexes it with the local embedding model.
up-local: db-start db-local-roles
	infra/local-stack.sh up-local
	cd apps/api && env -u SUPABASE_DB_ADMIN_URL uv run python -m scripts.reset_demo --local
	cd apps/api && LLM_PROVIDER=ollama uv run python -m scripts.reindex

# Checks the fully local stack against the real local services (F11-AC20)
smoke-local:
	infra/smoke-local.sh

# Checks the running local stack: start page, API with database, test IdP
smoke:
	infra/smoke.sh

# Local-only passwords of the login roles (the same the tests use)
db-local-roles:
	cd apps/api && uv run python -m scripts.local_db_roles

down:
	infra/local-stack.sh down
