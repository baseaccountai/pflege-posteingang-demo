#!/usr/bin/env bash
# Local stack with plain Docker, no Compose plugin needed (F11-AC5).
#
#   infra/local-stack.sh up        web + api with real providers and IdP from .env
#   infra/local-stack.sh up-test   web + api + test OIDC server, fake OCR/LLM, fixed local
#                                  secrets - no account and no key needed
#   infra/local-stack.sh up-local  everything on this machine (F11-AC13): Keycloak, Docling,
#                                  Ollama (runs natively), no .env, no cloud account
#   infra/local-stack.sh check-ollama  only the Ollama check of up-local (F11-AC14)
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
KEYCLOAK_IMAGE=quay.io/keycloak/keycloak:26.8.0
DOCLING_IMAGE=quay.io/docling-project/docling-serve-cpu:v1.37.0
KEYCLOAK_ISSUER=http://localhost:18100/realms/pflege
OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://localhost:11434}
OLLAMA_CHAT_MODEL=${OLLAMA_CHAT_MODEL:-qwen3:8b}
OLLAMA_EMBED_MODEL=${OLLAMA_EMBED_MODEL:-bge-m3}
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
  docker rm -f "$PREFIX-web" "$PREFIX-api" "$PREFIX-oidc" "$PREFIX-keycloak" "$PREFIX-docling" \
    >/dev/null 2>&1 || true
}

# F11-AC14: Ollama runs natively; without it (or a model) nothing else is started.
check_ollama() {
  local tags missing=()
  if ! tags=$(curl -fsS --max-time 5 "$OLLAMA_BASE_URL/api/tags" 2>/dev/null); then
    echo "Ollama läuft nicht ($OLLAMA_BASE_URL). Starten: ollama serve" >&2
    echo "(oder als Dienst: sudo systemctl start ollama)" >&2
    return 1
  fi
  for model in "$OLLAMA_CHAT_MODEL" "$OLLAMA_EMBED_MODEL"; do
    # Ollama lists "bge-m3:latest" for "bge-m3".
    if ! python3 -c 'import json,sys; m=sys.argv[1]; names={n["name"] for n in json.load(sys.stdin)["models"]}; sys.exit(0 if m in names or m+":latest" in names else 1)' \
      "$model" <<<"$tags"; then
      missing+=("$model")
    fi
  done
  if ((${#missing[@]})); then
    echo "Ollama-Modell fehlt. Laden:" >&2
    for model in "${missing[@]}"; do echo "  ollama pull $model" >&2; done
    return 1
  fi
  echo "ok    Ollama mit $OLLAMA_CHAT_MODEL und $OLLAMA_EMBED_MODEL"
}

wait_for() { # name url seconds
  local name=$1 url=$2 seconds=$3
  for _ in $(seq 1 $((seconds / 3))); do
    curl -fsS --max-time 5 "$url" >/dev/null 2>&1 && { echo "ok    $name"; return 0; }
    sleep 3
  done
  echo "FEHLER $name startet nicht ($url) - docker logs $PREFIX-${name,,}" >&2
  return 1
}

# Local agent key (self_signed, ADR 0012 "Lokal"): made once, kept outside git.
agent_key() {
  local key=infra/.local/agent-signing-key.pem
  if [[ ! -f $key ]]; then
    mkdir -p infra/.local
    openssl ecparam -name prime256v1 -genkey -noout 2>/dev/null |
      openssl pkcs8 -topk8 -nocrypt -out "$key"
    chmod 600 "$key"
  fi
  cat "$key"
}

memory_hint() {
  local free_gb
  free_gb=$(awk '/MemAvailable/ {printf "%d", $2 / 1048576}' /proc/meminfo)
  if ((free_gb < 10)); then
    echo "Hinweis: nur ${free_gb} GB Arbeitsspeicher frei; empfohlen sind etwa 10 GB" >&2
    echo "(Keycloak, Docling, Ollama mit $OLLAMA_CHAT_MODEL). Andere Container oder Programme schließen." >&2
  fi
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
  check-ollama)
    check_ollama
    ;;
  up-local)
    check_ollama
    memory_hint
    down
    build
    run keycloak -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
      -e KC_HTTP_PORT=18100 -e KC_HOSTNAME=http://localhost:18100 \
      -v "$PWD/infra/keycloak/pflege-realm.json:/opt/keycloak/data/import/pflege-realm.json:ro" \
      "$KEYCLOAK_IMAGE" start-dev --import-realm
    run docling -e DOCLING_SERVE_ENABLE_UI=false "$DOCLING_IMAGE"
    # Keycloak needs about 75 s on a laptop, Docling loads its models.
    wait_for Keycloak "$KEYCLOAK_ISSUER/.well-known/openid-configuration" 240
    wait_for Docling http://localhost:5001/health 240
    LOCAL_LLM=(-e LLM_PROVIDER=ollama -e OCR_PROVIDER=docling
      -e OLLAMA_BASE_URL="$OLLAMA_BASE_URL" -e OLLAMA_CHAT_MODEL="$OLLAMA_CHAT_MODEL"
      -e OLLAMA_EMBED_MODEL="$OLLAMA_EMBED_MODEL" -e DOCLING_BASE_URL=http://localhost:5001
      # qwen3:8b on a CPU-only laptop: ~4 tokens/s in, ~1.3 tokens/s out (01.11.2026).
      -e OLLAMA_TIMEOUT_SECONDS=1800 -e AGENT_MAX_SECONDS=600)
    run api "${LOCAL_DB[@]}" "${LOCAL_LLM[@]}" \
      -e OIDC_ISSUER=$KEYCLOAK_ISSUER -e OIDC_AUDIENCE=pflege-api -e OIDC_ROLES_CLAIM=roles \
      -e BFF_API_SECRET=local-bff-api-secret-at-least-32-bytes \
      -e AGENT_TOKEN_MODE=self_signed -e AGENT_ID=pflege-agent-local \
      -e "AGENT_SIGNING_KEY=$(agent_key)" "$PREFIX-api"
    run web "${LOCAL_DB[@]}" \
      -e OIDC_ISSUER=$KEYCLOAK_ISSUER -e OIDC_ROLES_CLAIM=roles \
      -e BFF_API_SECRET=local-bff-api-secret-at-least-32-bytes \
      -e APP_ORIGIN=http://localhost:3000 -e API_BASE_URL=http://127.0.0.1:8000 \
      -e OIDC_CLIENT_ID=pflege-web -e OIDC_CLIENT_SECRET=pflege-web-local-only-secret \
      -e API_WAIT_SECONDS=1800 \
      -e "OIDC_SCOPES=openid profile offline_access" \
      -e SESSION_ENC_KEY=BwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc= "$PREFIX-web"
    echo "Web: http://localhost:3000  Keycloak: $KEYCLOAK_ISSUER"
    echo "Anmelden wie öffentlich: pflege-wb1 / Pflege-WB1-Demo! (Liste auf der Startseite)"
    ;;
  down)
    down
    echo "Lokaler Stack gestoppt (Supabase läuft weiter: make db-stop)."
    ;;
  *)
    echo "Aufruf: infra/local-stack.sh up|up-test|up-local|check-ollama|down" >&2
    exit 2
    ;;
esac
