#!/bin/bash
# Collect observability data for debugging and support tickets
# Usage: bash scripts/collect-observability-data.sh
# Output: observability-report-YYYYMMDD-HHMMSS.txt

set -e

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
REPORT="observability-report-${TIMESTAMP}.txt"

echo "🔍 Collecting observability data..." >&2
echo "📝 Report will be saved to: $REPORT" >&2
echo ""

{
    # Header
    echo "╔════════════════════════════════════════════════╗"
    echo "║   IoT Hub Alpha - Observability Data Report    ║"
    echo "╚════════════════════════════════════════════════╝"
    echo ""
    echo "Collection Time: $(date)"
    echo "System: $(uname -a)"
    echo ""

    # === ENVIRONMENT ===
    echo "═══════════════════════════════════════════════"
    echo "ENVIRONMENT"
    echo "═══════════════════════════════════════════════"
    echo ""
    echo "Docker Version:"
    docker --version
    echo ""
    echo "Docker Compose Version:"
    docker compose --version
    echo ""
    echo "Disk Usage:"
    df -h | grep -E '^/|^Filesystem'
    echo ""

    # === SERVICE STATUS ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "SERVICE STATUS"
    echo "═══════════════════════════════════════════════"
    echo ""
    docker compose ps
    echo ""

    # === HEALTH ENDPOINTS ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "HEALTH CHECK RESULTS"
    echo "═══════════════════════════════════════════════"
    echo ""

    echo "Testing /health/ endpoint:"
    if curl -s -m 5 http://localhost:8000/health/ 2>&1; then
        echo ""
    else
        echo "(No response)"
        echo ""
    fi

    echo "Testing /ready/ endpoint:"
    if curl -s -m 5 http://localhost:8000/ready/ 2>&1; then
        echo ""
    else
        echo "(No response)"
        echo ""
    fi

    # === METRICS ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "METRICS ENDPOINT SAMPLE"
    echo "═══════════════════════════════════════════════"
    echo ""
    if curl -s -m 5 http://localhost:8000/metrics/ 2>&1 | head -80; then
        echo ""
    else
        echo "(No metrics endpoint available)"
        echo ""
    fi

    # === PROMETHEUS STATUS ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "PROMETHEUS TARGETS"
    echo "═══════════════════════════════════════════════"
    echo ""
    if curl -s -m 5 http://localhost:9090/api/v1/targets 2>&1 | python3 -m json.tool 2>/dev/null; then
        echo ""
    else
        echo "(Prometheus not responding)"
        echo ""
    fi

    # === LOGS ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "RECENT LOGS (Last 50 lines)"
    echo "═══════════════════════════════════════════════"
    echo ""

    echo "--- Django (web) ---"
    docker compose logs web --tail 50 2>/dev/null || echo "(No logs available)"
    echo ""

    echo "--- Prometheus ---"
    docker compose logs prometheus --tail 30 2>/dev/null || echo "(No logs available)"
    echo ""

    echo "--- Grafana ---"
    docker compose logs grafana --tail 20 2>/dev/null || echo "(No logs available)"
    echo ""

    # === DOCKER STATS ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "CONTAINER RESOURCE USAGE"
    echo "═══════════════════════════════════════════════"
    echo ""
    docker stats --no-stream 2>/dev/null || echo "(Docker stats unavailable)"
    echo ""

    # === FILESYSTEM ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "DOCKER VOLUMES & STORAGE"
    echo "═══════════════════════════════════════════════"
    echo ""
    docker volume ls 2>/dev/null | grep -E 'prometheus|grafana|postgres' || echo "(No volumes found)"
    echo ""

    # === NETWORK ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "DOCKER NETWORK"
    echo "═══════════════════════════════════════════════"
    echo ""
    docker network inspect iot_hub_net 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "(Network info unavailable)"
    echo ""

    # === SUMMARY ===
    echo ""
    echo "═══════════════════════════════════════════════"
    echo "QUICK DIAGNOSTICS"
    echo "═══════════════════════════════════════════════"
    echo ""

    echo "Web Service:"
    if docker compose ps web | grep -q "Up"; then
        echo "  Status: ✅ Running"
        if curl -sf http://localhost:8000/health/ > /dev/null 2>&1; then
            echo "  Health: ✅ Responding"
        else
            echo "  Health: ❌ Not responding"
        fi
    else
        echo "  Status: ❌ Not running"
    fi
    echo ""

    echo "Database Service:"
    if docker compose ps db | grep -q "Up"; then
        echo "  Status: ✅ Running"
    else
        echo "  Status: ❌ Not running"
    fi
    echo ""

    echo "Prometheus Service:"
    if docker compose ps prometheus | grep -q "Up"; then
        echo "  Status: ✅ Running"
        if curl -sf http://localhost:9090 > /dev/null 2>&1; then
            echo "  Health: ✅ Responding"
        else
            echo "  Health: ❌ Not responding"
        fi
    else
        echo "  Status: ❌ Not running"
    fi
    echo ""

    echo "Grafana Service:"
    if docker compose ps grafana | grep -q "Up"; then
        echo "  Status: ✅ Running"
        if curl -sf http://localhost:3000 > /dev/null 2>&1; then
            echo "  Health: ✅ Responding"
        else
            echo "  Health: ❌ Not responding"
        fi
    else
        echo "  Status: ❌ Not running"
    fi
    echo ""

    # === END ===
    echo "═══════════════════════════════════════════════"
    echo "Report generated: $(date)"
    echo "═══════════════════════════════════════════════"

} > "$REPORT"

echo ""
echo "✅ Report saved to: $REPORT" >&2
echo ""
echo "To view the report:"
echo "  cat $REPORT"
echo ""
echo "To send in a support ticket, include this file."
echo ""

# Also output to stdout
cat "$REPORT"
