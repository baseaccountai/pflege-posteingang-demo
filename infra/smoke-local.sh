#!/usr/bin/env bash
# Smoke test of the fully local stack (F11-AC20):  make up-local && make smoke-local
# Start page, API in local mode, Keycloak, Docling - then a probe against the real local
# models (apps/api/scripts/local_probe.py): OCR, field suggestion, tool call, embedding.
set -euo pipefail
cd "$(dirname "$0")/.."

WEB_URL=${WEB_URL:-http://localhost:3000}
API_URL=${API_URL:-http://localhost:8000}
KEYCLOAK_ISSUER=${KEYCLOAK_ISSUER:-http://localhost:18100/realms/pflege}
DOCLING_URL=${DOCLING_URL:-http://localhost:5001}

check() {
  local name=$1 url=$2 expected=$3
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 "$url" 2>/dev/null | grep -q -- "$expected"; then
      echo "ok    $name"
      return 0
    fi
    sleep 2
  done
  echo "FEHLER $name: $url enthält nicht '$expected'" >&2
  return 1
}

check "Startseite mit Banner" "$WEB_URL/" "MUSTERDATEN"
check "API und Datenbank" "$API_URL/health/ready" '"db":"ok"'
check "API nutzt Ollama" "$API_URL/health" '"llm_provider":"ollama"'
check "API nutzt Docling" "$API_URL/health" '"ocr_provider":"docling"'
check "Agent lokal (self_signed)" "$API_URL/health" '"agent_token":"self_signed"'
check "Keycloak (Discovery)" "$KEYCLOAK_ISSUER/.well-known/openid-configuration" "\"issuer\":\"$KEYCLOAK_ISSUER\""
check "Docling" "$DOCLING_URL/health" '"ok"'
(cd apps/api && LLM_PROVIDER=ollama OCR_PROVIDER=docling DOCLING_BASE_URL="$DOCLING_URL" \
  uv run python -m scripts.local_probe)
echo "Lokaler Betrieb komplett läuft."
