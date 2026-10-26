.PHONY: setup test test-api test-web test-db db-start db-stop db-reset e2e lint up down

COMPOSE := docker compose -f infra/docker-compose.yml
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

# Needs the local Supabase stack (make db-start), Docker (test OIDC server) and uv (API)
e2e:
	cd apps/web && pnpm e2e

lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check .
	cd apps/web && pnpm lint

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down
