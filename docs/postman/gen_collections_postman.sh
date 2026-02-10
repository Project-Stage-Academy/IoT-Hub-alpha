#!/usr/bin/env bash
set -euo pipefail

SPEC_PATH="${1:-docs/api.yaml}"
OUT_DIR="${2:-artifacts}"
POSTMAN_OUT="${OUT_DIR}/postman_collection.json"

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "==> $*"; }

command -v node >/dev/null 2>&1 || die "Missing required command: node"
command -v npm  >/dev/null 2>&1 || die "Missing required command: npm"

[ -f "${SPEC_PATH}" ] || die "OpenAPI spec not found: ${SPEC_PATH}"
mkdir -p "${OUT_DIR}"

info "Generating Postman collection via OpenAPI Generator"
npx --yes @openapitools/openapi-generator-cli generate \
  -i "${SPEC_PATH}" \
  -g postman-collection \
  -o "${OUT_DIR}" \
  --additional-properties=folderStrategy=Tags,requestParameterGeneration=Example

# openapi-generator outputs a collection file with a fixed name in many versions;
# normalize it to POSTMAN_OUT
FOUND="$(ls -1 "${OUT_DIR}"/*.json 2>/dev/null | head -n 1 || true)"
[ -n "${FOUND}" ] || die "Could not find generated collection json in ${OUT_DIR}"
cp "${FOUND}" "${POSTMAN_OUT}"

info "Postman collection generated: ${POSTMAN_OUT}"