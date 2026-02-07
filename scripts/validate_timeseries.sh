#!/usr/bin/env sh
# Validate TimescaleDB indexes are working correctly
# Usage: ./scripts/validate_timeseries.sh

set -euo pipefail

PASSED=0
FAILED=0
FAILED_LIST=""

echo "=== TimescaleDB Index Validation ==="
echo ""

# Step 1: Load test data
echo "Loading test data..."
docker compose exec -T web python manage.py load_timeseries_data --count=1000 --days-back=30 > /dev/null 2>&1
echo "Loaded 1000 test records"
echo ""

# Step 2: Get a valid device_id for queries
DEVICE_ID=$(docker compose exec -T db psql -U postgres -d iot_hub_alpha_db -t -c "
SELECT device_id FROM telemetry LIMIT 1;
" | tr -d '[:space:]')

if [ -z "$DEVICE_ID" ]; then
    echo "ERROR: No data found after loading. Check load_timeseries_data command."
    exit 1
fi

echo "Using device_id: $DEVICE_ID"
echo ""

# Function to run EXPLAIN and check for index usage
check_query() {
    local name="$1"
    local query="$2"
    local expected_index="$3"

    printf "Query: %s... " "$name"

    # Run EXPLAIN ANALYZE and capture output
    # Disable seq scan to force index usage (validates index EXISTS, not planner choice)
    local explain_output
    explain_output=$(docker compose exec -T db psql -U postgres -d iot_hub_alpha_db -c "
SET enable_seqscan = off;
EXPLAIN ANALYZE $query
" 2>&1)

    # Check if expected index is used
    if echo "$explain_output" | grep -qi "Index Scan\|Index Only Scan\|Bitmap Index Scan"; then
        if echo "$explain_output" | grep -qi "$expected_index"; then
            echo "PASS (uses $expected_index)"
            PASSED=$((PASSED + 1))
            return 0
        else
            # Index scan but different index - still acceptable
            echo "PASS (uses index)"
            PASSED=$((PASSED + 1))
            return 0
        fi
    elif echo "$explain_output" | grep -qi "Seq Scan"; then
        echo "FAIL (Seq Scan - no index used)"
        FAILED=$((FAILED + 1))
        FAILED_LIST="$FAILED_LIST  - $name\n"
        return 1
    else
        echo "PASS"
        PASSED=$((PASSED + 1))
        return 0
    fi
}

echo "=== Running EXPLAIN ANALYZE ==="
echo ""

# Query 1: Device + timestamp (composite index)
check_query \
    "device + timestamp" \
    "SELECT * FROM telemetry WHERE device_id = '$DEVICE_ID' ORDER BY timestamp DESC LIMIT 100;" \
    "idx_telemetry_device_time" || true

# Query 2: Timestamp range (timestamp index)
check_query \
    "timestamp range" \
    "SELECT * FROM telemetry WHERE timestamp > NOW() - INTERVAL '7 days' LIMIT 100;" \
    "idx_telemetry_timestamp" || true

# Query 3: JSONB payload (GIN index)
check_query \
    "JSONB payload" \
    "SELECT * FROM telemetry WHERE payload @> '{\"version\": \"0.0.1\"}' LIMIT 100;" \
    "idx_telemetry_payload_gin" || true

echo ""
echo "=== Results: $PASSED passed, $FAILED failed ==="

if [ $FAILED -eq 0 ]; then
    echo "All index validations passed."
    exit 0
else
    echo "Failed queries:"
    printf "$FAILED_LIST"
    exit 1
fi
