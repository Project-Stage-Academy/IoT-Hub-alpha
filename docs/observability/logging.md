# Structured JSON Logging Guide

## Overview

The IoT Hub Alpha application uses structured JSON logging for both Django and Celery, providing rich context and making logs queryable and analyzable. All logs include timestamps, log levels, request IDs, and contextual information.

**Status**: ✅ Implementation Complete (AC1)

---

## Quick Start

### View Live Logs

```bash
# View Django application logs
docker compose logs -f web

# View Celery worker logs
docker compose logs -f worker

# View all logs including Prometheus and Grafana
docker compose logs -f
```

### View Last N Lines

```bash
# Last 100 lines
docker compose logs web --tail 100

# Last 50 lines for worker
docker compose logs worker --tail 50
```

### Filter Logs by Pattern

```bash
# View only ERROR messages
docker compose logs web | grep ERROR

# View logs from specific timeframe
docker compose logs --since 2026-01-27T12:00:00 --until 2026-01-27T13:00:00 web

# View logs containing specific request
docker compose logs web | grep "request_id.*abc123"
```

---

## JSON Log Format

### Django HTTP Request Logs

```json
{
  "timestamp": "2026-01-27T13:30:00.123456",
  "level": "INFO",
  "logger": "django.request",
  "message": "GET /api/devices/ HTTP/1.1",
  "request_id": "a1b2c3d4-e5f6-4789-a012-bc3456789def",
  "method": "GET",
  "path": "/api/devices/",
  "status_code": 200,
  "content_length": 1024,
  "duration_ms": 45.67,
  "user_id": 42,
  "ip_address": "127.0.0.1"
}
```

**Key Fields**:
- `timestamp`: When the request occurred (ISO 8601 format)
- `level`: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `logger`: Which component logged this (e.g., django.request)
- `request_id`: Unique ID to trace this request through system
- `method`: HTTP method (GET, POST, PUT, etc.)
- `path`: Request path/endpoint
- `status_code`: HTTP response status (200, 404, 500, etc.)
- `duration_ms`: How long request took (milliseconds)
- `user_id`: Authenticated user ID (if available)
- `ip_address`: Client IP address

### Celery Task Logs

```json
{
  "timestamp": "2026-01-27T13:30:15.234567",
  "level": "INFO",
  "logger": "celery.task",
  "message": "Task started",
  "task_name": "apps.core.tasks.process_device_data",
  "task_id": "f1e2d3c4-b5a6-4789-a012-bc3456789abc",
  "request_id": "a1b2c3d4-e5f6-4789-a012-bc3456789def",
  "queue": "default",
  "status": "started",
  "args": ["device_123"],
  "kwargs": {}
}
```

**Key Fields**:
- `timestamp`: When task was logged
- `level`: Log level
- `task_name`: Full task function name
- `task_id`: Unique ID for this task execution
- `request_id`: Related HTTP request (if triggered by request)
- `queue`: Which Celery queue (default, high-priority, etc.)
- `status`: Task status (started, success, failure)
- `args`: Task positional arguments
- `kwargs`: Task keyword arguments

### Task Completion Log

```json
{
  "timestamp": "2026-01-27T13:30:20.456789",
  "level": "INFO",
  "logger": "celery.task",
  "message": "Task completed",
  "task_name": "apps.core.tasks.process_device_data",
  "task_id": "f1e2d3c4-b5a6-4789-a012-bc3456789abc",
  "status": "success",
  "duration_ms": 5234.56,
  "result": "Processed 150 records"
}
```

### Error Logs

```json
{
  "timestamp": "2026-01-27T13:30:25.567890",
  "level": "ERROR",
  "logger": "django.request",
  "message": "Internal server error",
  "request_id": "a1b2c3d4-e5f6-4789-a012-bc3456789def",
  "path": "/api/devices/",
  "method": "POST",
  "status_code": 500,
  "exception_type": "DatabaseError",
  "exception_message": "Connection pool exhausted",
  "traceback": "Traceback (most recent call last):\n  File ..."
}
```

**Key Fields**:
- `exception_type`: Type of exception (DatabaseError, ValueError, etc.)
- `exception_message`: Error message
- `traceback`: Full stack trace for debugging

---

## Querying Logs

### View Logs in Docker

#### Real-time logs

```bash
# Follow logs as they arrive
docker compose logs -f web

# Follow with timestamps
docker compose logs -f --timestamps web

# Follow with extra detail
docker compose logs -f --timestamps --details web
```

#### Search in Logs

```bash
# Find all ERROR logs
docker compose logs web | grep ERROR

# Find logs by request ID
docker compose logs web | grep "a1b2c3d4-e5f6"

# Find slow requests (duration > 1000ms)
docker compose logs web | grep -oP '"duration_ms":\s*\d+' | awk -F: '{if ($2 > 1000) print}'

# Find failed tasks
docker compose logs worker | grep '"status":\s*"failure"'

# Find logs in time range (last 5 minutes)
docker compose logs --since 5m web

# Find logs from specific service
docker compose logs prometheus

# Combine multiple filters
docker compose logs web | grep ERROR | grep -v "404\|400"
```

### Advanced Log Queries

#### Extract JSON and Parse

```bash
# Convert Docker logs to JSON array and parse with jq
docker compose logs web --timestamps=false | grep -o '{.*}' | jq '.[] | select(.level=="ERROR")'

# Get error rate
docker compose logs web --since 1h | grep -o '{.*}' | jq -s '[.[] | select(.level=="ERROR")] | length'

# Top endpoints by request count
docker compose logs web | grep -o '{.*}' | jq '[.[] | .path] | group_by(.) | map({path: .[0], count: length}) | sort_by(-.count) | .[0:5]'
```

#### Find Specific Issues

```bash
# Database connection errors
docker compose logs web | grep -i "database\|connection\|pool"

# Authentication failures
docker compose logs web | grep "401\|403\|permission"

# Performance issues (slow requests)
docker compose logs web | grep -oP '"duration_ms":\s*\d+' | awk -F: '{if ($2 > 500) print "Slow request: " $0}'

# Task failures in Celery
docker compose logs worker | grep '"status":\s*"failure"'

# Queue backlog
docker compose logs worker | grep -i "queue\|backlog\|pending"
```

---

## Log Levels

### DEBUG (10)

Detailed information for diagnosing problems.

```bash
docker compose logs web | grep '"level":\s*"DEBUG"'
```

**Example**:
```json
{
  "level": "DEBUG",
  "message": "Database query executed",
  "sql": "SELECT * FROM device WHERE id = %s",
  "execution_time_ms": 2.34
}
```

### INFO (20)

General informational messages about program execution.

```bash
docker compose logs web | grep '"level":\s*"INFO"'
```

**Example**:
```json
{
  "level": "INFO",
  "message": "GET /api/devices/ completed",
  "status_code": 200,
  "duration_ms": 45.67
}
```

### WARNING (30)

Warning messages about potentially problematic situations.

```bash
docker compose logs web | grep '"level":\s*"WARNING"'
```

**Example**:
```json
{
  "level": "WARNING",
  "message": "Database query slow",
  "duration_ms": 2500.0,
  "threshold_ms": 1000.0
}
```

### ERROR (40)

Error messages about serious problems.

```bash
docker compose logs web | grep '"level":\s*"ERROR"'
```

**Example**:
```json
{
  "level": "ERROR",
  "message": "Failed to process request",
  "exception_type": "DatabaseError",
  "exception_message": "Connection pool exhausted"
}
```

### CRITICAL (50)

Critical messages about the most serious problems.

```bash
docker compose logs web | grep '"level":\s*"CRITICAL"'
```

**Example**:
```json
{
  "level": "CRITICAL",
  "message": "Service unable to start",
  "reason": "Database initialization failed"
}
```

---

## Collecting Logs for Support

### Create a Support Bundle

When reporting issues, collect logs and metrics:

```bash
#!/bin/bash
# scripts/collect-observability-data.sh

TIMESTAMP=$(date -u +"%Y%m%d-%H%M%S")
OUTPUT_DIR="observability-bundle-${TIMESTAMP}"

mkdir -p "$OUTPUT_DIR"

echo "Collecting observability data..."

# Service status
docker compose ps > "$OUTPUT_DIR/docker-compose-ps.txt"

# Recent logs (last 100 lines)
docker compose logs --tail 100 web > "$OUTPUT_DIR/logs-web.json"
docker compose logs --tail 100 worker > "$OUTPUT_DIR/logs-worker.json"
docker compose logs --tail 100 prometheus > "$OUTPUT_DIR/logs-prometheus.txt"
docker compose logs --tail 100 grafana > "$OUTPUT_DIR/logs-grafana.txt"
docker compose logs --tail 100 db > "$OUTPUT_DIR/logs-db.txt"

# Prometheus metrics
curl http://localhost:9090/api/v1/query?query=up > "$OUTPUT_DIR/prometheus-targets.json" 2>/dev/null
curl http://localhost:8000/metrics/ > "$OUTPUT_DIR/django-metrics.txt" 2>/dev/null

# System information
docker stats --no-stream > "$OUTPUT_DIR/docker-stats.txt"
df -h > "$OUTPUT_DIR/disk-usage.txt"

# Configuration
cp docker-compose.yml "$OUTPUT_DIR/docker-compose.yml"
cp devops/prometheus.yml "$OUTPUT_DIR/prometheus.yml"

# Archive
tar -czf "${OUTPUT_DIR}.tar.gz" "$OUTPUT_DIR"
echo "✅ Bundle saved: ${OUTPUT_DIR}.tar.gz"

# Cleanup
rm -rf "$OUTPUT_DIR"
```

### Run Support Script

```bash
bash scripts/collect-observability-data.sh

# Sends observability-bundle-20260127-123456.tar.gz to support
```

---

## Common Log Patterns

### Find High-Latency Requests

```bash
# Requests taking more than 1 second
docker compose logs --since 1h web | grep -o '{.*}' | jq 'select(.duration_ms > 1000)' | grep path
```

### Monitor Error Rate

```bash
# Count errors vs successes in last hour
docker compose logs --since 1h web | grep -o '{.*}' | jq '[.[] | .status_code] | group_by(.) | map({status: .[0], count: length})'
```

### Track Request by ID

```bash
# Follow a specific request through system
REQUEST_ID="a1b2c3d4-e5f6"
docker compose logs | grep "$REQUEST_ID"
```

### Celery Task Tracking

```bash
# Find task and its logs
TASK_ID="f1e2d3c4-b5a6"
docker compose logs worker | grep "$TASK_ID"
```

### Database Query Performance

```bash
# Find slow database queries
docker compose logs web | grep -i "query\|duration" | jq 'select(.duration_ms > 500)'
```

---

## Troubleshooting Log Issues

### Issue: No JSON in Logs

**Problem**: Logs appear as plain text instead of JSON

**Solution**:
1. Ensure Django is using JSON logging formatter
2. Check `backend/config/settings/base.py` LOGGING configuration
3. Restart containers: `docker compose restart web`

### Issue: Logs Not Appearing

**Problem**: `docker compose logs` returns empty

**Solution**:
```bash
# Verify containers are running
docker compose ps

# Check if services started properly
docker compose logs web

# Rebuild and restart
docker compose build web
docker compose up -d web
```

### Issue: Logs Cut Off

**Problem**: Logs contain `...` and seem truncated

**Solution**:
```bash
# Get full logs without truncation
docker compose logs web | less

# Or redirect to file for full content
docker compose logs web > full-logs.txt
```

---

## Log Retention

### Docker Log Rotation

Configure in `docker-compose.yml` (already configured):

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"        # Max file size
    max-file: "3"          # Keep 3 rotated files
```

**Result**: ~30MB max logs per service (10m × 3)

### Cleanup Old Logs

```bash
# Remove logs older than 7 days
find /var/lib/docker/containers/*/logs/ -type f -mtime +7 -delete

# Or cleanup all Docker logs
docker system prune
```

---

## Best Practices

1. **Always include request_id in queries**
   - Helps trace requests across services
   - Example: `docker compose logs | grep "request_id.*abc123"`

2. **Use structured fields for filtering**
   - Don't parse raw text
   - Use JSON parsing: `jq .level, .path, .status_code`

3. **Monitor error logs regularly**
   - Set up log aggregation for production
   - Alert on ERROR and CRITICAL levels

4. **Archive logs for compliance**
   - Keep logs for at least 30 days
   - Use log aggregation service (ELK, Splunk, etc.)

5. **Correlate logs with metrics**
   - Use request_id to find logs when metrics spike
   - Check Prometheus/Grafana dashboards alongside logs

---

## References

- [Django Logging Documentation](https://docs.djangoproject.com/en/stable/topics/logging/)
- [Python JSON Logging](https://docs.python.org/3/library/json.html)
- [Docker Logs Documentation](https://docs.docker.com/config/containers/logging/)
- [jq JSON Query Tool](https://stedolan.github.io/jq/)

---

## Acceptance Criteria (AC1)

### ✅ Django and Celery produce structured JSON logs by default

- Django application logs HTTP requests in JSON format
- Celery worker logs task execution in JSON format
- Both include timestamps, request IDs, and contextual information

**Enabled in**:
- `backend/config/settings/base.py` - LOGGING configuration
- `backend/config/celery.py` - Celery logging setup

### ✅ docs/observability/logging.md explains log fields

- JSON field reference documented above
- Log levels documented
- Examples provided for each log type

### ✅ How to query logs

- Command examples for Docker logs
- Advanced jq queries for JSON log analysis
- Filtering and searching techniques

---

**AC1 Acceptance Criteria**: ✅ COMPLETE

- [x] Structured JSON logging in Django
- [x] Structured JSON logging in Celery
- [x] Log fields documented
- [x] Log query examples provided