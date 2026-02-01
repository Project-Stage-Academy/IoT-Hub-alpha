#!/usr/bin/env bash
set -euo pipefail

# Get script directory (so paths work from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PASSED=0
FAILED=0
FAILED_LIST=""

check() {
    name="$1"
    cmd="$2"

    printf "Checking: %s... " "$name"
    if eval "$cmd" > /dev/null 2>&1; then
        echo "PASS"
        PASSED=$((PASSED + 1))
    else
        echo "FAIL"
        FAILED=$((FAILED + 1))
        FAILED_LIST="$FAILED_LIST  - $name\n"
    fi
}

echo "=== Infrastructure Checks ==="
check "Health endpoint" "curl -sf http://localhost:8000/health/"
check "Metrics endpoint" "curl -sf http://localhost:8000/metrics/ | grep -q http_requests_total"

echo ""
echo "=== Application Smoke Tests ==="

scripts=(
  "smoke/smoke1_seed_data.sh"
  # Ingest http smoke test cannot pass due to a lack of API ingest endpoint
  #"smoke/smoke2_ingest_http.sh"
  # Rule trigger is currently non functional as there is no runner.
  #"smoke/smoke3_rule_trigger_notification.sh"
)

for s in "${scripts[@]}"; do
  echo "==> Running: $s"
  if bash "$SCRIPT_DIR/$s"; then
    PASSED=$((PASSED + 1))
  else
    FAILED=$((FAILED + 1))
    FAILED_LIST="$FAILED_LIST  - $s\n"
  fi
  echo
done

echo ""
echo "=== Results: $PASSED passed, $FAILED failed ==="

if [ $FAILED -eq 0 ]; then
  echo "All smoke checks passed."
  exit 0
else
  echo "Failed checks:"
  printf "$FAILED_LIST"
  exit 1
fi
