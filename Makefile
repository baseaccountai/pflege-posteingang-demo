.PHONY: setup test test-api test-web e2e lint up down

COMPOSE := docker compose -f infra/docker-compose.yml

# One-time install of all dependencies (incl. Playwright browser)
setup:
	cd apps/api && uv sync --frozen
	cd apps/web && pnpm install --frozen-lockfile && pnpm exec playwright install chromium

test: test-api test-web

test-api:
	cd apps/api && uv run pytest -v

test-web:
	cd apps/web && pnpm test

e2e:
	cd apps/web && pnpm e2e

lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check .
	cd apps/web && pnpm lint

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down
