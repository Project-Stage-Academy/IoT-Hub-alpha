#!/usr/bin/env bash
set -euo pipefail

# ---- Config (adjust if your paths/ports differ) ----
SPEC_PATH="${SPEC_PATH:-docs/api.yaml}"
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

echo "==> 3) Run contract tests against mock"
chmod +x scripts/contract-smoke.sh
timeout "$HARD_TIMEOUT" env \
  scripts/contract-smoke.sh

echo "✅ All checks passed"
