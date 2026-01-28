# Monitoring Stack Setup & Usage Guide

## Overview

This guide shows how to set up and use the complete monitoring stack for IoT Hub Alpha, including Prometheus for metrics collection and Grafana for visualization.

**Quick Start**: 5 minutes
**Full Setup**: 15 minutes
**Advanced Configuration**: 30 minutes

---

## Part 1: Quick Start (5 Minutes)

### Step 1: Start Services

```bash
cd /path/to/IoT-Hub-Alpha

# Start complete monitoring stack
docker compose up -d db redis web worker prometheus grafana

# Or with monitoring profile
docker compose --profile monitoring up -d
```

### Step 2: Verify Services

```bash
# Check all services running
docker compose ps

# Expected output:
# iot_hub_web    Up (healthy)
# iot_hub_db     Up (healthy)
# iot_hub_prometheus  Up
# iot_hub_grafana     Up
```

### Step 3: Access Services

```
Django Metrics:  http://localhost:8000/metrics/
Prometheus:      http://localhost:9090
Grafana:         http://localhost:3000 (admin/admin)
```

### Step 4: View Dashboard

1. Open http://localhost:3000
2. Login: `admin` / `admin`
3. Go to **Dashboards** → **Browse**
4. Click **IoT Hub Alpha - Observability**

That's it! Your monitoring dashboard is ready. 🎉

---

## Part 2: Full Setup

### Prerequisites

- Docker & Docker Compose installed
- 4GB free disk space
- Ports available: 8000 (Django), 9090 (Prometheus), 3000 (Grafana)

### Step 1: Verify Django Metrics Endpoint

```bash
# Make some test requests
curl http://localhost:8000/
curl http://localhost:8000/health/
curl http://localhost:8000/ready/

# Check metrics are being collected
curl http://localhost:8000/metrics/ | head -30

# Expected output:
# # HELP http_requests_total Total HTTP requests
# # TYPE http_requests_total counter
# http_requests_total{endpoint="/",method="GET",status="200"} 1.0
```

### Step 2: Verify Prometheus Scraping

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Look for:
# "health": "up"  ← Django target is healthy
# "lastError": "" ← No errors

# Or visit UI
http://localhost:9090/targets
```

### Step 3: Configure Grafana Data Source

#### Option A: UI (Recommended)

1. Open http://localhost:3000
2. Login with `admin` / `admin`
3. Click **Configuration** (⚙️) → **Data Sources**
4. Click **Add data source**
5. Select **Prometheus**
6. Set URL: `http://prometheus:9090`
7. Click **Save & Test**

#### Option B: Docker Environment

Edit `docker-compose.yml`:
```yaml
grafana:
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=your_secure_password
    - GF_SECURITY_ADMIN_USER=admin
```

### Step 4: Import Dashboard

#### Method 1: Upload JSON File

1. In Grafana, click **+** → **Import**
2. Click **Upload JSON file**
3. Select `docs/observability/grafana-dashboard.json`
4. Select **Prometheus** data source
5. Click **Import**

#### Method 2: API Call

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d @docs/observability/grafana-dashboard.json \
  -u admin:admin \
  http://localhost:3000/api/dashboards/db
```

### Step 5: Generate Test Data

Make requests to populate metrics:

```bash
# Make various requests
for i in {1..10}; do
  curl http://localhost:8000/
  curl http://localhost:8000/health/
  curl http://localhost:8000/metrics/
  sleep 1
done

# View updated metrics
curl http://localhost:8000/metrics/ | grep http_requests_total
```

### Step 6: View Metrics in Grafana

1. Open Grafana dashboard
2. Wait 1-2 minutes for data to appear
3. Panels should show:
   - Request rate increasing
   - Latency distribution
   - Error rates (0% if all requests succeeded)

---

## Part 3: Adding New Metrics

### How to Add a Custom Metric

#### Step 1: Define Metric

**File**: `backend/config/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge

# Define your metric
MY_REQUESTS = Counter(
    'my_requests_total',
    'Total requests to my endpoint',
    ['endpoint', 'status']
)

MY_LATENCY = Histogram(
    'my_request_duration_seconds',
    'Request latency',
    ['endpoint'],
    buckets=(0.1, 0.5, 1.0, 5.0)
)

ACTIVE_CONNECTIONS = Gauge(
    'my_active_connections',
    'Number of active connections',
    ['connection_type']
)
```

#### Step 2: Record Metrics in Code

**In Middleware** (for all requests):
```python
# backend/config/middleware.py
from .metrics import MY_REQUESTS, MY_LATENCY

def __call__(self, request):
    start = time.time()
    response = self.get_response(request)

    # Record metrics
    latency = time.time() - start
    MY_LATENCY.labels(endpoint=request.path).observe(latency)
    MY_REQUESTS.labels(
        endpoint=request.path,
        status=response.status_code
    ).inc()

    return response
```

**In Views** (for specific endpoints):
```python
# backend/apps/core/views.py
from config.metrics import MY_REQUESTS

def my_view(request):
    MY_REQUESTS.labels(endpoint='/my-endpoint', status='200').inc()
    return HttpResponse("OK")
```

**In Celery Tasks**:
```python
# backend/apps/core/tasks.py
from config.metrics import MY_REQUESTS

@shared_task
def my_task():
    try:
        # Do work
        MY_REQUESTS.labels(task='my_task', status='success').inc()
    except Exception:
        MY_REQUESTS.labels(task='my_task', status='failure').inc()
        raise
```

**In Signals**:
```python
# backend/apps/core/signals.py
from django.db.models.signals import post_save
from config.metrics import MY_REQUESTS

@receiver(post_save, sender=MyModel)
def on_model_save(sender, instance, created, **kwargs):
    if created:
        MY_REQUESTS.labels(action='create', model='MyModel').inc()
```

#### Step 3: Restart Services

```bash
docker compose restart web

# Verify metric is exposed
curl http://localhost:8000/metrics/ | grep my_requests
```

#### Step 4: Create PromQL Queries

Test your queries in Prometheus:

```bash
# Open http://localhost:9090

# Test query
my_requests_total

# Aggregated by endpoint
sum by (endpoint) (rate(my_requests_total[5m]))

# Error rate
sum(rate(my_requests_total{status=~"5.."}[5m])) / sum(rate(my_requests_total[5m]))
```

#### Step 5: Add Panel to Grafana

1. Open your dashboard
2. Click **Add panel** (top left)
3. Click **Add** (new panel)
4. In **Metrics** section:
   - Data source: `Prometheus`
   - Query: `sum(rate(my_requests_total[5m]))`
5. Set Title: "My Requests per Second"
6. Click **Apply**
7. Click **Save dashboard**

---

## Part 4: Common Workflows

### View Request Latency for Specific Endpoint

```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{endpoint="/api/devices"}[5m]))
```

### Find Endpoints with Most Errors

```promql
topk(5, sum by (endpoint) (rate(http_requests_total{status=~"5.."}[5m])))
```

### Check Celery Task Performance

```promql
histogram_quantile(0.95, rate(celery_task_duration_seconds_bucket[5m]))
```

### Monitor Database Query Performance

```promql
# (if django.db.connection_time metric is available)
rate(django_db_connection_time_seconds[5m])
```

### Check Service Health

```promql
up{job="django"}  # 1 = healthy, 0 = down
```

---

## Part 5: Monitoring Strategy

### Metrics to Watch

**Always Monitor**:
1. Request rate: `rate(http_requests_total[5m])`
2. Error rate: `rate(http_requests_total{status=~"5.."}[5m])`
3. Latency: `histogram_quantile(0.95, ...)`
4. Service health: `up{job="django"}`

**Regularly Check**:
1. Celery queue length
2. Database connection pool
3. CPU and memory usage
4. Disk space

**Debug When Needed**:
1. Slow requests: Check P95/P99 latencies
2. Error spikes: Check logs + error endpoints
3. Queue backup: Check Celery metrics + worker logs

### Setting Alerts

Example alerts (to be added to prometheus.yml):
```yaml
groups:
  - name: iot_hub
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1.0
        for: 10m

      - alert: ServiceDown
        expr: up{job="django"} == 0
        for: 1m
```

---

## Part 6: Troubleshooting

### Metrics Not Appearing

1. **Make requests to generate data**:
   ```bash
   curl http://localhost:8000/
   sleep 5
   ```

2. **Check metrics endpoint**:
   ```bash
   curl http://localhost:8000/metrics/ | grep http_requests_total
   ```

3. **Check Prometheus scraping**:
   ```bash
   curl http://localhost:9090/api/v1/targets
   # Look for "health": "up"
   ```

4. **Check time range in Grafana**:
   - Click time picker (top right)
   - Select "Last 1 hour" or "Last 5 minutes"

### No Data in Panels

1. **Verify Prometheus data source**:
   - Grafana → Settings → Data Sources
   - Click Prometheus
   - Click "Test"

2. **Check Prometheus logs**:
   ```bash
   docker compose logs prometheus | tail -20
   ```

3. **Test query directly**:
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=http_requests_total'
   ```

### Performance Issues

1. **Reduce metric cardinality**:
   - Avoid high-cardinality labels (user_id, request_id)
   - Use bounded labels

2. **Adjust refresh rates**:
   - Grafana: 30s-1m instead of 5s
   - Prometheus: 30s-1m instead of 10s

3. **Limit Prometheus storage**:
   - Set retention: `--storage.tsdb.retention.time=7d`
   - Reduce scrape frequency for less critical targets

---

## Summary

✅ **Part 1: Quick Start** - 5 min
- Start services
- Access dashboards
- View real-time metrics

✅ **Part 2: Full Setup** - 15 min
- Configure Prometheus
- Configure Grafana
- Import dashboard

✅ **Part 3: Add Metrics** - 30 min per metric
- Define metric
- Record in code
- Create queries
- Add to dashboard

✅ **Part 4-6: Operations** - Ongoing
- Monitor dashboards
- Debug issues
- Optimize performance

---

## Next Steps

1. **Set up alerts**: Add alert rules to `devops/prometheus.yml`
2. **Create more dashboards**: Clone for different services
3. **Export data**: Archive metrics to long-term storage
4. **Integrate with paging**: Set up PagerDuty/OpsGenie alerts
5. **Custom dashboards**: Create team-specific views

---

## Acceptance Criteria (AC7)

### ✅ docs/observability/ contains clear instructions

- [x] `setup-guide.md` - This file
- [x] `grafana-setup.md` - Grafana-specific guide
- [x] `metrics.md` - Part 1 metrics reference
- [x] `prometheus-setup.md` - Prometheus configuration
- [x] `healthchecks.md` - Health check documentation
- [x] `verification-checklist.md` - Testing procedures

### ✅ How to start Prometheus and Grafana

```bash
docker compose up -d db redis web worker prometheus grafana
```

### ✅ How to access dashboards

- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

### ✅ How to add new metrics

See **Part 3: Adding New Metrics** section above

---

**AC7 Acceptance Criteria**: ✅ COMPLETE
