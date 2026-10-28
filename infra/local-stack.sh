#!/usr/bin/env bash
# Local stack with plain Docker, no Compose plugin needed (F11-AC5).
#
#   infra/local-stack.sh up        web + api with real providers and IdP from .env
#   infra/local-stack.sh up-test   web + api + test OIDC server, fake OCR/LLM, fixed local
#                                  secrets - no account and no key needed
#   infra/local-stack.sh down
#
# Called by `make up`, `make up-test`, `make down` (which also start the local Supabase).
# Host networking: browser, containers and the local Supabase (127.0.0.1:56322) reach each
# other as "localhost", so the OIDC issuer URL is the same for the browser and the BFF.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE=${1:-}
PREFIX=pp-local
OIDC_IMAGE=ghcr.io/navikt/mock-oauth2-server:2.1.10
TEST_ISSUER=http://localhost:18090/default # e2e uses 18080, so both can run at once

# Local-only passwords of the database login roles - the same the tests set
# (apps/api/scripts/local_db_roles.py); never used for the cloud database.
LOCAL_DB=(
  -e DATABASE_URL=postgresql://api_gateway:api_gateway_local_test@127.0.0.1:56322/postgres
  -e BFF_DATABASE_URL=postgresql://bff_session:bff_session_local_test@127.0.0.1:56322/postgres
)
# Fixed secrets for the test mode only.
TEST_SECRETS=(
  -e OIDC_ISSUER=$TEST_ISSUER
  -e OIDC_ROLES_CLAIM=roles
  -e BFF_API_SECRET=local-bff-api-secret-at-least-32-bytes
)

down() {
  docker rm -f "$PREFIX-web" "$PREFIX-api" "$PREFIX-oidc" >/dev/null 2>&1 || true
}

build() {
  echo "Baue Images (beim ersten Mal einige Minuten) …"
  docker build --quiet --tag "$PREFIX-api" apps/api >/dev/null
  docker build --quiet --tag "$PREFIX-web" apps/web >/dev/null
}

run() { # name image [docker run options...]
  local name=$1
  shift
  docker run --detach --name "$PREFIX-$name" --network host --restart unless-stopped "$@" >/dev/null
}

# .env for `up`: comments and inline comments removed (docker's --env-file would keep them
# as part of the value). The temporary copy is deleted right after the containers start.
env_file() {
  local cleaned
  cleaned=$(mktemp)
  chmod 600 "$cleaned"
  if [[ -f .env ]]; then
    sed -E 's/[[:space:]]+#.*$//; /^[[:space:]]*(#|$)/d' .env >"$cleaned"
  fi
  echo "$cleaned"
}

case "$MODE" in
  up)
    down
    build
    ENV_FILE=$(env_file)
    trap 'rm -f "$ENV_FILE"' EXIT
    run api --env-file "$ENV_FILE" "${LOCAL_DB[@]}" "$PREFIX-api"
    run web --env-file "$ENV_FILE" "${LOCAL_DB[@]}" \
      -e APP_ORIGIN=http://localhost:3000 -e API_BASE_URL=http://127.0.0.1:8000 "$PREFIX-web"
    echo "Web: http://localhost:3000  API: http://localhost:8000"
    ;;
  up-test)
    down
    build
    run oidc -e SERVER_PORT=18090 -e JSON_CONFIG_PATH=/config/config.json \
      -v "$PWD/infra/oidc-mock:/config:ro" "$OIDC_IMAGE"
    run api "${LOCAL_DB[@]}" "${TEST_SECRETS[@]}" \
      -e LLM_PROVIDER=fake -e OCR_PROVIDER=fake -e FAKE_OCR_SAMPLES=/samples \
      -e OIDC_AUDIENCE=default -e RAG_MIN_SIMILARITY=0.1 \
      -v "$PWD/samples:/samples:ro" "$PREFIX-api"
    run web "${LOCAL_DB[@]}" "${TEST_SECRETS[@]}" \
      -e APP_ORIGIN=http://localhost:3000 -e API_BASE_URL=http://127.0.0.1:8000 \
      -e OIDC_CLIENT_ID=pflege-local -e OIDC_CLIENT_SECRET=local-client-secret \
      -e "OIDC_SCOPES=openid profile offline_access" \
      -e SESSION_ENC_KEY=BwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc= "$PREFIX-web"
    echo "Web: http://localhost:3000  Test-IdP: $TEST_ISSUER"
    echo "Anmelden: beliebiger Name, Claims z. B. {\"roles\": [\"nurse_wb1\"]}"
    ;;
  down)
    down
    echo "Lokaler Stack gestoppt (Supabase läuft weiter: make db-stop)."
    ;;
  *)
    echo "Aufruf: infra/local-stack.sh up|up-test|down" >&2
    exit 2
    ;;
esac
