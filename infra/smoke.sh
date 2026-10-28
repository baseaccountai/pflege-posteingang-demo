#!/usr/bin/env bash
# Smoke test of the local stack (F11-AC5): start page, API with database, test IdP.
#   make up-test && make smoke
# Waits up to 90 s for each part (images start slowly the first time).
set -euo pipefail

WEB_URL=${WEB_URL:-http://localhost:3000}
API_URL=${API_URL:-http://localhost:8000}
OIDC_ISSUER_URL=${OIDC_ISSUER_URL:-http://localhost:18090/default}

check() {
  local name=$1 url=$2 expected=$3
  for _ in $(seq 1 45); do
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
check "Test-OIDC-Server (Discovery)" "$OIDC_ISSUER_URL/.well-known/openid-configuration" "\"issuer\" *: *\"$OIDC_ISSUER_URL\""
echo "Lokaler Stack läuft."
