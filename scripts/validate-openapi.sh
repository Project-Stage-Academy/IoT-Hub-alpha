#!/usr/bin/env bash
set -euo pipefail

# ---- Config (adjust if your paths/ports differ) ----
SPEC_PATH="${SPEC_PATH:-docs/api.yaml}"
COLLECTION_PATH="${COLLECTION_PATH:-docs/postman/postman_collection.json}"

HOST="${HOST:-iot-industry.redocly.app}"
PORT="${PORT:-80}"

# IMPORTANT: Redocly mock base path includes /_mock/<path-to-spec-dir>/ (depends on your project layout).
# If your requests already include the full mock path in {{baseUrl}}, you can just set:
# BASE_URL="http://${HOST}:${PORT}"
# Otherwise, set it explicitly to your mock base:
BASE_URL="${BASE_URL:-http://${HOST}:${PORT}/_mock/openapi}"

# Newman timeouts (ms)
TIMEOUT_REQUEST_MS="${TIMEOUT_REQUEST_MS:-10000}"  # 10s per request
TIMEOUT_RUN_MS="${TIMEOUT_RUN_MS:-300000}"         # 5m total
HARD_TIMEOUT="${HARD_TIMEOUT:-6m}"                 # kill newman if it hangs

# ---- Helpers ----
require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "❌ Missing required command: $1"
    echo "   Install it, e.g.: npm i -g @redocly/cli newman"
    exit 1
  }
}

cleanup() {
  if [[ -n "${PREVIEW_PID:-}" ]] && kill -0 "$PREVIEW_PID" >/dev/null 2>&1; then
    kill "$PREVIEW_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

# ---- Checks ----
require redocly
require newman
require curl

echo "==> 1) Lint OpenAPI: ${SPEC_PATH}"
redocly lint "$SPEC_PATH"

echo "==> 3) Run contract tests (Newman) against mock: ${BASE_URL}"
# Use CLI var injection even if collection already has variables; CI/local stays consistent.
timeout "$HARD_TIMEOUT" newman run "$COLLECTION_PATH" \
  --env-var "baseUrl=${BASE_URL}" \
  --timeout-request "$TIMEOUT_REQUEST_MS" \
  --timeout "$TIMEOUT_RUN_MS"

echo "✅ All checks passed"
