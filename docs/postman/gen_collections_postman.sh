#!/usr/bin/env bash
set -euo pipefail

SPEC_PATH="${1:-docs/api.yaml}"
OUT_DIR="${2:-artifacts}"
POSTMAN_OUT="${OUT_DIR}/postman_collection.json"

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "==> $*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

[ -f "${SPEC_PATH}" ] || die "OpenAPI spec not found: ${SPEC_PATH}"
mkdir -p "${OUT_DIR}"

need_cmd node
need_cmd npm

info "Generating Postman collection from ${SPEC_PATH} -> ${POSTMAN_OUT}"

npx --yes openapi-to-postmanv2 \
  -s "${SPEC_PATH}" \
  -o "${POSTMAN_OUT}" \
  -p

info "Postman collection generated: ${POSTMAN_OUT}"

echo "Artifacts:"
echo " - ${POSTMAN_OUT}"