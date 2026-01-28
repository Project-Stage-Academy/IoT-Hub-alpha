# Container Health Checks - Liveness & Readiness Probes

## Overview

This document describes the health check implementation for the IoT Hub Alpha application. Health checks allow container orchestration systems (Docker Compose, Kubernetes, etc.) to monitor service health and automatically restart unhealthy containers.

**Status**: ✅ Implementation Complete

---

## What Are Health Checks?

Health checks verify that containers are:

1. **Alive (Liveness)**: The process is running and responding
2. **Ready (Readiness)**: The service is ready to handle traffic

### Difference Between Liveness & Readiness

| Type | Purpose | Checks | Action if Failed |
|------|---------|--------|------------------|
| **Liveness** | Is the service running? | HTTP endpoint responds | Restart container |
| **Readiness** | Is the service ready? | Database connectivity | Remove from load balancer |

---

## Implementation

### File: `backend/scripts/healthcheck.sh`

```bash
#!/bin/bash
# Health check script for container orchestration
# Performs both liveness and readiness checks
# Exit 0 = healthy, Exit 1 = unhealthy

set -e

# Liveness probe: Check if HTTP endpoint responds
if ! curl -f http://localhost:8000/health/ > /dev/null 2>&1; then
    echo "Liveness check failed: HTTP health endpoint not responding"
    exit 1
fi

# Readiness probe: Check if database connectivity is available
if ! curl -f http://localhost:8000/ready/ > /dev/null 2>&1; then
    echo "Readiness check failed: Database not available"
    exit 1
fi

echo "Health checks passed: Service is healthy and ready"
exit 0
```

**What it does**:
1. Checks `/health/` endpoint → confirms Django process is running
2. Checks `/ready/` endpoint → confirms database is connected
3. Returns exit code 0 if all checks pass, 1 if any fail

---

### Endpoints

#### `GET /health/` - Liveness Probe

**Purpose**: Verify Django application is running

**Response**:
```
HTTP/1.1 200 OK
ok
```

**Implementation** (`backend/apps/core/views.py`):
```python
def health(request):  # noqa: ARG001
    """Liveness probe - checks if service is running."""
    return HttpResponse("ok")
```

**When to use**: Container orchestration, load balancer health checks

---

#### `GET /ready/` - Readiness Probe

**Purpose**: Verify service is ready to handle traffic (database connected)

**Response** (when ready):
```
HTTP/1.1 200 OK
ready
```

**Response** (when not ready):
```
HTTP/1.1 503 Service Unavailable
not ready
```

**Implementation** (`backend/apps/core/views.py`):
```python
def ready(request):  # noqa: ARG001
    """Readiness probe - checks if service is ready (DB connected)."""
    try:
        from django.db import connection
        connection.ensure_connection()
        return HttpResponse("ready", status=200)
    except Exception:
        return HttpResponse("not ready", status=503)
```

**When to use**: Load balancer routing, Kubernetes readiness probes

---

### Docker Compose Configuration

**File**: `docker-compose.yml`

```yaml
web:
  # ... other config ...
  healthcheck:
    test: ["CMD", "/app/scripts/healthcheck.sh"]
    interval: 30s         # Check every 30 seconds
    timeout: 5s           # Wait 5 seconds for response
    retries: 3            # Fail after 3 consecutive failures
    start_period: 10s     # Grace period after startup
```

**Configuration Details**:

| Setting | Value | Meaning |
|---------|-------|---------|
| `test` | `["CMD", "/app/scripts/healthcheck.sh"]` | Run script inside container |
| `interval` | `30s` | Check every 30 seconds |
| `timeout` | `5s` | Script must complete in 5 seconds |
| `retries` | `3` | Container unhealthy after 3 failed checks |
| `start_period` | `10s` | Grace period: don't count failures for first 10s |

---

## Health Check States

### Healthy ✅

```bash
$ docker compose ps
NAME              STATUS
iot_hub_web       Up (healthy)
iot_hub_db        Up (healthy)
```

**Means**:
- All endpoints responding
- Database is connected
- Service is ready for traffic

---

### Starting ⏳

```bash
$ docker compose ps
NAME              STATUS
iot_hub_web       Up (health: starting)
```

**Means**:
- Container just started
- Health checks haven't passed yet
- Still in `start_period` (first 10 seconds)

**Duration**: Up to 10 seconds (start_period)

---

### Unhealthy ❌

```bash
$ docker compose ps
NAME              STATUS
iot_hub_web       Up (unhealthy)
```

**Means**:
- Health check script failed
- 3 consecutive failures detected
- Container needs attention

**Possible causes**:
- Django crashed
- Database connection lost
- Port 8000 not responding
- Disk full or memory exhausted

**Action**: `docker compose logs web` to see details

---

## Verification

### Test Health Endpoints Manually

```bash
# Test liveness probe
curl http://localhost:8000/health/
# Response: ok (HTTP 200)

# Test readiness probe (when DB is up)
curl http://localhost:8000/ready/
# Response: ready (HTTP 200)

# Test readiness probe (when DB is down)
curl http://localhost:8000/ready/
# Response: not ready (HTTP 503)
```

### Check Docker Health Status

```bash
# View health status
docker compose ps

# Get detailed health info
docker inspect --format='{{json .State.Health}}' iot_hub_web | python3 -m json.tool

# Expected output:
{
  "Status": "healthy",
  "FailingStreak": 0,
  "LogOutput": "Health checks passed: Service is healthy and ready"
}
```

### Test Health Check Script

```bash
# Run inside container
docker compose exec web bash /app/scripts/healthcheck.sh

# Expected output:
# Health checks passed: Service is healthy and ready
# Exit code: 0
```

### Simulate Health Check Failure

```bash
# Stop database to trigger readiness failure
docker compose stop db

# Check status (web will become unhealthy after ~90 seconds)
docker compose ps
# Expected: iot_hub_web Up (unhealthy)

# View logs
docker compose logs web | grep -i "not ready\|database"

# Restart database
docker compose start db

# Web should return to healthy within 30 seconds
```

---

## Common Issues & Solutions

### Issue 1: Web Container Shows "Unhealthy"

**Symptoms**:
```bash
iot_hub_web    Up (unhealthy)
```

**Diagnosis**:
```bash
# Check logs
docker compose logs web | tail -20

# Check if health endpoints work
curl http://localhost:8000/health/
curl http://localhost:8000/ready/

# Check database connection
docker compose exec web python manage.py dbshell
```

**Solutions**:
1. Wait 10 seconds - might still be starting
2. Check logs for errors: `docker compose logs web`
3. Verify database is healthy: `docker compose ps db`
4. Restart container: `docker compose restart web`

---

### Issue 2: "Health Check Timeout"

**Symptoms**:
```
WARNING: Healthcheck for web timed out after 5 seconds
```

**Causes**:
- Django is slow to respond
- CPU is overloaded
- Disk I/O is slow

**Solutions**:
1. Increase timeout: Change `timeout: 5s` to `timeout: 10s` in docker-compose.yml
2. Check system resources: `docker stats`
3. Rebuild container: `docker compose build web`

---

### Issue 3: "Cannot connect to http://localhost:8000"

**Symptoms**:
```bash
curl: (7) Failed to connect to localhost:8000
```

**Causes**:
- Django not started yet (normal during startup)
- Port 8000 not exposed
- Container crashed

**Solutions**:
1. Check logs: `docker compose logs web`
2. Verify port mapping: `docker compose ps`
3. Restart container: `docker compose restart web`

---

## Integration with Orchestration

### Docker Compose

Health checks in Docker Compose:
- ✅ Monitor container status
- ✅ Show in `docker compose ps`
- ✅ Enable `condition: service_healthy` in depends_on
- ❌ Do NOT auto-restart (Docker daemon handles restarts)

```bash
# View all health statuses
docker compose ps

# Only start dependent service when web is healthy
depends_on:
  web:
    condition: service_healthy
```

### Kubernetes (Future)

Health checks translate to Kubernetes probes:

```yaml
livenessProbe:
  httpGet:
    path: /health/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30
```

---

## Acceptance Criteria (AC5)

### ✅ docker-compose.yml includes healthchecks

```yaml
web:
  healthcheck:
    test: ["CMD", "/app/scripts/healthcheck.sh"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 10s

db:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
    interval: 5s
    timeout: 5s
    retries: 5
```

### ✅ Healthchecks cause service status to reflect readiness and liveness

```bash
# Healthy services
$ docker compose ps
iot_hub_web  Up (healthy)
iot_hub_db   Up (healthy)

# Web shows unhealthy when DB is down
$ docker compose stop db
$ docker compose ps
iot_hub_web  Up (unhealthy)
iot_hub_db   Exited
```

---

## Monitoring Health Checks

### View Health Check Logs

```bash
# Get health check history
docker inspect iot_hub_web | jq '.State.Health.Log[-5:]'

# Expected output:
[
  {
    "Start": "2026-01-25T13:30:00.123Z",
    "End": "2026-01-25T13:30:00.456Z",
    "ExitCode": 0,
    "Output": "Health checks passed..."
  }
]
```

### Query Health via REST API

```bash
# Get full health information
curl http://localhost:8000/health/
curl http://localhost:8000/ready/

# Get container health
docker exec iot_hub_web curl http://localhost:8000/ready/
```

---

## Best Practices

1. **Always use readiness probes**: Ensures traffic only goes to ready instances
2. **Set appropriate timeouts**: Balance between responsiveness and false positives
3. **Log health check results**: Aids in debugging
4. **Test failure scenarios**: Verify behavior when services are unhealthy
5. **Monitor health check trends**: Track frequency of failures over time

---

## References

- [Docker Compose Healthcheck Documentation](https://docs.docker.com/compose/compose-file/compose-file-v3/#healthcheck)
- [Kubernetes Probe Documentation](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- [Health Check Patterns](https://www.docker.com/blog/dockerfile-best-practices-2/)

---

## Summary

- ✅ Liveness probe: `/health/` - checks if service is running
- ✅ Readiness probe: `/ready/` - checks if service is ready (DB connected)
- ✅ Health check script: `backend/scripts/healthcheck.sh` - runs both checks
- ✅ Docker Compose: Uses health check script with appropriate intervals and timeouts
- ✅ Status visible in: `docker compose ps` shows (healthy) or (unhealthy)

**AC5 Acceptance Criteria**: ✅ COMPLETE

All requirements met:
- [x] Healthchecks for web service
- [x] Healthchecks for db service
- [x] Readiness probe checks DB connectivity
- [x] Liveness probe checks HTTP endpoint
- [x] Status reflects readiness and liveness in `docker compose ps`
