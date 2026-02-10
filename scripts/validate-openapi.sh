#!/usr/bin/env bash
set -euo pipefail

# ---- Config ----
SPEC_PATH="${SPEC_PATH:-docs/api.yaml}"

POSTMAN_COLLECTION="${POSTMAN_COLLECTION:-docs/postman/postman_collection.json}"

PRISM_HOST="${PRISM_HOST:-127.0.0.1}"
PRISM_PORT="${PRISM_PORT:-4010}"

# This MUST match your OpenAPI servers url (/api/v1)
# and MUST match what your Postman env uses as {{baseUrl}}
BASE_URL="${BASE_URL:-http://${PRISM_HOST}:${PRISM_PORT}}"

HARD_TIMEOUT="${HARD_TIMEOUT:-1m}"

# ---- Helpers ----
require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "❌ Missing required command: $1"
    echo "   Install it, e.g.: npm i -g @redocly/cli newman"
    exit 1
  }
}

cleanup() {
  if [[ -n "${PRISM_PID:-}" ]] && kill -0 "$PRISM_PID" >/dev/null 2>&1; then
    kill "$PRISM_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

wait_for_http() {
  local url="$1"
  local tries="${2:-40}"
  local sleep_s="${3:-0.25}"

  for _ in $(seq 1 "$tries"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$sleep_s"
  done

  return 1
}

# ---- Checks ----
require redocly
require newman
require curl
require node
require npm

[[ -f "$SPEC_PATH" ]] || { echo "❌ OpenAPI spec not found: $SPEC_PATH"; exit 1; }
[[ -f "$POSTMAN_COLLECTION" ]] || { echo "❌ Postman collection not found: $POSTMAN_COLLECTION"; exit 1; }

echo "==> 1) Lint OpenAPI: ${SPEC_PATH}"
redocly lint "$SPEC_PATH"

echo "==> 2) Start Prism mock server: ${SPEC_PATH} on ${PRISM_HOST}:${PRISM_PORT}"
# --dynamic helps Prism generate bodies if examples are missing
# Redirect output to keep CI logs clean (remove redirection if debugging)
npx --yes @stoplight/prism-cli mock "$SPEC_PATH" \
  --dynamic \
  -h "$PRISM_HOST" \
  -p "$PRISM_PORT" \
  >/tmp/prism.log 2>&1 &
PRISM_PID=$!

# Wait until Prism is reachable
# Prism returns 404 for "/" sometimes; we just need *any* HTTP response.
# We'll probe a real path from your API to avoid false negatives.
echo "==> 3) Wait for Prism to be ready..."
if ! wait_for_http "${BASE_URL}/auth/fake" 60 0.25; then
  echo "❌ Prism did not become ready."
  echo "---- Prism log (tail) ----"
  tail -n 200 /tmp/prism.log || true
  exit 1
fi

echo "==> 4) Inject 2xx tests into collection"
python scripts/postman_rule_inject.py "$POSTMAN_COLLECTION"

echo "==> 5) Run Newman against Prism"
# Ensure your Postman env contains baseUrl = http://127.0.0.1:4010/api/v1
# (or whatever BASE_URL is)
timeout "$HARD_TIMEOUT" newman run "$POSTMAN_COLLECTION" \
  --env-var "baseUrl=${BASE_URL}" \
  --color off

echo "✅ All checks passed"