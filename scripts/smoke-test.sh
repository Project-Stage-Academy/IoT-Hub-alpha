#!/usr/bin/env sh
set -e  # Exit on first failure

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

PASSED=0
FAILED=0

check() {
    name="$1"
    cmd="$2"

    printf "Checking: %s... " "$name"
    if eval "$cmd" > /dev/null 2>&1; then
        printf "${GREEN}PASS${NC}\n"
        PASSED=$((PASSED + 1))
    else
        printf "${RED}FAIL${NC}\n"
        FAILED=$((FAILED + 1))
    fi
}

printf "=== IoT Hub Smoke Tests ===\n"

check "Seed data valid" "docker compose exec -T web python manage.py seed_data --dry_run"
check "Metrics endpoint" "curl -sf http://localhost:8000/metrics/ | grep -q http_requests_total"

printf "\n"
printf "=== Results: %d passed, %d failed ===\n" "$PASSED" "$FAILED"

[ $FAILED -eq 0 ] && exit 0 || exit 1
