#!/usr/bin/env sh
# Validate TimescaleDB indexes are working correctly
# Usage: ./scripts/validate_timeseries.sh [--cleanup]

set -euo pipefail

# Database connection (uses env vars with defaults)
DB_USER="${POSTGRES_USER:-postgres}"
DB_NAME="${POSTGRES_DB:-iot_hub_alpha_db}"
PSQL_CMD="docker compose exec -T db psql -U $DB_USER -d $DB_NAME"

# Parse arguments
CLEANUP=false
for arg in "$@"; do
    case $arg in
        --cleanup) CLEANUP=true ;;
    esac
done

PASSED=0
FAILED=0
FAILED_LIST=""

echo "=== TimescaleDB Index Validation ==="
echo ""

# Step 1: Load test data
echo "Loading test data..."
if ! output=$(docker compose exec -T web python manage.py load_timeseries_data --count=1000 --days-back=30 2>&1); then
    echo "ERROR: Failed to load test data:"
    echo "$output"
    exit 1
fi
echo "Loaded test records"
echo ""

# Step 2: Get a valid device_id for queries
DEVICE_ID=$($PSQL_CMD -t -c "SELECT device_id FROM telemetry ORDER BY device_id LIMIT 1;" | tr -d '[:space:]')

if [ -z "$DEVICE_ID" ]; then
    echo "ERROR: No data found after loading. Check load_timeseries_data command."
    exit 1
fi

echo "Using device_id: $DEVICE_ID"
echo ""

# Step 3: Verify indexes exist
echo "=== Verifying Indexes Exist ==="
echo ""

check_index_exists() {
    local index_name="$1"
    printf "Index: %s... " "$index_name"

    if $PSQL_CMD -t -c "SELECT 1 FROM pg_indexes WHERE indexname = '$index_name';" | grep -q 1; then
        echo "EXISTS"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo "MISSING"
        FAILED=$((FAILED + 1))
        FAILED_LIST="$FAILED_LIST  - $index_name\n"
        return 1
    fi
}

check_index_exists "idx_telemetry_device_time" || true
check_index_exists "idx_telemetry_payload_gin" || true
check_index_exists "telemetry_timestamp_idx" || true

echo ""

# Step 4: Verify queries use indexes
echo "=== Running EXPLAIN ANALYZE ==="
echo ""

check_query() {
    local name="$1"
    local query="$2"

    printf "Query: %s... " "$name"

    # Run EXPLAIN ANALYZE and capture output
    # Disable seq scan to force index usage (validates indexes work, not planner choice)
    local explain_output
    explain_output=$($PSQL_CMD -c "
SET enable_seqscan = off;
EXPLAIN ANALYZE $query
" 2>&1)

    # Check if any index is used (not seq scan)
    if echo "$explain_output" | grep -qi "Index Scan\|Index Only Scan\|Bitmap Index Scan"; then
        echo "PASS (uses index)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo "FAIL (no index used)"
        FAILED=$((FAILED + 1))
        FAILED_LIST="$FAILED_LIST  - $name\n"
        return 1
    fi
}

# Query 1: Device + timestamp (composite index)
check_query \
    "device + timestamp" \
    "SELECT * FROM telemetry WHERE device_id = '$DEVICE_ID' ORDER BY timestamp DESC LIMIT 100;" || true

# Query 2: Timestamp range (timestamp index)
check_query \
    "timestamp range" \
    "SELECT * FROM telemetry WHERE timestamp > NOW() - INTERVAL '7 days' LIMIT 100;" || true

# Query 3: JSONB payload (GIN index)
check_query \
    "JSONB payload" \
    "SELECT * FROM telemetry WHERE payload @> '{\"version\": \"0.0.1\"}' LIMIT 100;" || true

echo ""
echo "=== Results: $PASSED passed, $FAILED failed ==="

# Cleanup test data if requested
if [ "$CLEANUP" = true ]; then
    echo ""
    echo "Cleaning up test data..."
    $PSQL_CMD -c "
        DELETE FROM telemetry WHERE device_id IN (
            SELECT id FROM devices WHERE serial_number LIKE 'LOADTEST-%'
        );
        DELETE FROM devices WHERE serial_number LIKE 'LOADTEST-%';
        DELETE FROM device_types WHERE name LIKE 'Test %';
    " > /dev/null
    echo "Test data removed."
fi

if [ $FAILED -eq 0 ]; then
    echo "All index validations passed."
    exit 0
else
    echo "Failed queries:"
    printf "$FAILED_LIST"
    exit 1
fi
