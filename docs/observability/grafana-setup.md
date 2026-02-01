# Grafana Setup & Dashboard Import Guide

## Overview

Grafana is a visualization and dashboarding platform that displays metrics from Prometheus in real-time graphs and tables. This guide covers installation, configuration, and dashboard setup for the IoT Hub Alpha monitoring stack.

**Status**: ✅ Dashboard JSON Ready for Import

---

## Quick Start (5 minutes)

### 1. Start Grafana Container

```bash
docker compose up -d grafana
```

### 2. Access Grafana UI

```
http://localhost:3000
```

### 3. Login with Default Credentials

```
Username: admin
Password: admin
```

### 4. Add Prometheus Data Source

1. Click **Configuration** (gear icon) → **Data Sources**
2. Click **Add data source**
3. Select **Prometheus**
4. Set **URL**: `http://prometheus:9090`
5. Click **Save & Test**

### 5. Import Dashboard

1. Click **+** (Create) → **Import**
2. Upload: `docs/observability/grafana-dashboard.json`
3. Select **Prometheus** as data source
4. Click **Import**

### 6. View Dashboard

Dashboard appears with 5 panels showing real-time metrics!

---

## Detailed Setup

### Prerequisites

- Docker and Docker Compose installed
- Prometheus running on port 9090
- Django app running on port 8000 with metrics endpoint

### Step 1: Start Monitoring Stack

```bash
# Start all services including Grafana
docker compose up -d db redis web worker prometheus grafana

# Or start specific services
docker compose --profile monitoring up -d

# Verify Grafana is running
docker compose ps grafana
```

**Expected Output**:
```
iot_hub_grafana  Up (healthy)  3000/tcp
```

### Step 2: Verify Services are Running

```bash
# Check Prometheus
curl http://localhost:9090/api/v1/targets

# Check Django metrics
curl http://localhost:8000/metrics/ | head -10

# Check Grafana
curl http://localhost:3000/api/health
```

### Step 3: Configure Data Source

#### Option A: Via UI (Recommended)

1. Open http://localhost:3000
2. Login: `admin` / `admin`
3. Go to **Settings** (gear icon)
4. Select **Data Sources**
5. Click **Add data source**
6. Choose **Prometheus**
7. Set URL: `http://prometheus:9090`
8. Click **Save & Test**

#### Option B: Via Environment (Docker)

Add to `docker-compose.yml`:
```yaml
grafana:
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=yourpassword
    - GF_USERS_ALLOW_SIGN_UP=false
    - GF_AUTH_ANONYMOUS_ENABLED=true
```

### Step 4: Import Dashboard

#### Option A: From File

1. Click **Dashboards** → **New** → **Import**
2. Click **Upload JSON file**
3. Select `docs/observability/grafana-dashboard.json`
4. Select **Prometheus** data source
5. Click **Import**

#### Option B: From JSON Content

1. Click **Dashboards** → **New** → **Import**
2. Paste JSON content from `grafana-dashboard.json`
3. Click **Load**
4. Select **Prometheus** data source
5. Click **Import**

#### Option C: Via REST API

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d @docs/observability/grafana-dashboard.json \
  http://admin:admin@localhost:3000/api/dashboards/db
```

### Step 5: Verify Dashboard

1. Open http://localhost:3000/d/iot-hub-alpha-observability
2. Verify all 5 panels display data
3. Wait 1-2 minutes for graphs to populate with data
4. Panels should update every 10 seconds

---

## Dashboard Panels

### Panel 1: Request Rate (requests/sec)

**Metric**: `http_requests_total`

**Shows**:
- Total request rate
- Success rate (2xx)
- Client errors (4xx)
- Server errors (5xx)

**Interpretation**:
- Flat/increasing line: Normal traffic
- Sudden spike: Traffic surge or new feature
- Drop to zero: Service down

**Alert Threshold**:
- Warning: > 1000 req/sec
- Critical: > 5000 req/sec (or service down)

---

### Panel 2: Error Rate (%)

**Metric**: `http_requests_total` (by status code)

**Shows**:
- 4xx error percentage
- 5xx error percentage

**Interpretation**:
- 0-1%: Normal
- 1-5%: Elevated errors (investigate)
- > 5%: Critical (immediate action needed)

**Common Causes**:
- 4xx: Client errors (bad requests, auth failures)
- 5xx: Server errors (crashes, bugs, resource exhaustion)

---

### Panel 3: Request Latency (ms)

**Metric**: `http_request_duration_seconds_bucket`

**Shows**:
- P50 latency (median)
- P95 latency (95th percentile)
- P99 latency (99th percentile)

**Interpretation**:
- P50 < 50ms: Good
- P95 < 200ms: Acceptable
- P99 < 500ms: Watch for degradation
- P99 > 1000ms: Performance issue

**Common Causes**:
- Database queries slow
- Large response sizes
- CPU throttling
- I/O bottleneck

---

### Panel 4: Celery Tasks (by status)

**Metric**: `celery_tasks_total`

**Shows**:
- Successful tasks completed
- Failed tasks by task name

**Interpretation**:
- Increasing success line: Normal operation
- Failures appear: Background tasks failing
- Flat line: No tasks running

**Common Issues**:
- Task failures: Check logs for exceptions
- Queue backup: Celery workers too slow
- Task hangups: Worker process crashed

---

### Panel 5: Request Distribution by Endpoint

**Metric**: `http_requests_total` (by endpoint and status)

**Shows**:
- Request rate per endpoint
- Broken down by HTTP status code

**Interpretation**:
- Identifies hottest endpoints
- Shows which endpoints have errors
- Helps with capacity planning

**Example**:
```
/api/devices (200): 850 req/s
/api/data (200):    450 req/s
/metrics/ (200):    100 req/s
/health/ (200):      50 req/s
/api/devices (500):   10 req/s  ← Error endpoint
```

---

## Configuration Options

### Time Range

**Default**: Last 1 hour

**Change**:
1. Click **time picker** (top right)
2. Select **Last 6 hours**, **Last 24 hours**, etc.
3. Or set custom range

**Recommended**:
- Real-time monitoring: Last 5 minutes
- Daily review: Last 24 hours
- Trend analysis: Last 7 days

### Refresh Rate

**Default**: Auto (30 seconds)

**Change**:
1. Click **refresh icon** (top right)
2. Select interval: 5s, 10s, 30s, 1m, 5m, etc.

**Recommended**:
- Development: 10s
- Production: 30s
- Low-traffic: 1m

### Panel Configuration

**Edit panel**:
1. Hover over panel title
2. Click **gear icon** → **Edit**
3. Modify PromQL query
4. Adjust visualization options
5. Click **Apply**

---

## Adding Metrics to Dashboard

### Step 1: Define Metric in Code

```python
# backend/config/metrics.py
MY_METRIC = Counter(
    'my_custom_metric_total',
    'Description',
    ['label1', 'label2']
)
```

### Step 2: Record Metric

```python
# Somewhere in your code
MY_METRIC.labels(label1='value1', label2='value2').inc()
```

### Step 3: Create PromQL Query

```promql
sum(rate(my_custom_metric_total[5m])) by (label1)
```

### Step 4: Add Panel to Dashboard

1. Open dashboard
2. Click **Add panel** (top left)
3. Click **Add** (new panel)
4. Enter PromQL query
5. Set visualization type
6. Configure options
7. Click **Apply**
8. Click **Save dashboard**

---

## Troubleshooting

### Issue 1: Grafana Not Starting

**Symptoms**:
```bash
docker compose logs grafana | tail -20
# Error: Connection refused
```

**Solutions**:
```bash
# Check if port 3000 is in use
lsof -i :3000

# Restart Grafana
docker compose restart grafana

# Check logs
docker compose logs -f grafana
```

---

### Issue 2: Data Source Connection Error

**Symptoms**:
```
Error: Datasource "Prometheus" is not connected
```

**Solutions**:
1. Verify Prometheus is running: `curl http://localhost:9090`
2. Check data source URL: Should be `http://prometheus:9090` (not localhost)
3. If using docker-compose: `http://prometheus:9090` (service name)
4. If using localhost: `http://localhost:9090`

**Test connection**:
```bash
# From host
curl http://localhost:9090/api/v1/query?query=up

# From Grafana container
docker compose exec grafana curl http://prometheus:9090/api/health
```

---

### Issue 3: No Data in Panels

**Symptoms**:
```
"No data"
```

**Causes & Solutions**:
1. **Metrics not being collected**
   - Make test requests: `curl http://localhost:8000/`
   - Check metrics: `curl http://localhost:8000/metrics/`

2. **Prometheus not scraping**
   - Check targets: http://localhost:9090/targets
   - Verify Django target is "UP"

3. **Wrong time range**
   - Extend time range: Click time picker → "Last 6 hours"
   - Make requests to generate data

4. **Invalid PromQL query**
   - Open Prometheus: http://localhost:9090
   - Test query in Expression box
   - Fix syntax errors

---

### Issue 4: Panels Show Old Data

**Symptoms**:
```
Graphs not updating
```

**Solutions**:
1. Refresh browser: `Ctrl+R` or `Cmd+R`
2. Adjust refresh rate: Click refresh icon → select interval
3. Force refresh: Click refresh icon immediately
4. Check Prometheus data: `curl http://localhost:9090/api/v1/targets`

---

## Exporting & Sharing

### Export as Image

1. Hover over panel
2. Click **share icon**
3. Click **Save as PNG**
4. Send to team

### Export as PDF

1. Click dashboard name
2. Click **...** (more options)
3. Click **Download as PDF**

### Share Dashboard URL

**Public URL** (requires Grafana configuration):
```
http://your-domain:3000/d/iot-hub-alpha-observability
```

**Current Development URL**:
```
http://localhost:3000/d/iot-hub-alpha-observability
```

---

## Security

### Change Default Admin Password

1. Click **Configuration** (gear)
2. Click **Users**
3. Click **admin**
4. Click **Edit**
5. Change password
6. Click **Update**

### Disable Anonymous Access

1. Click **Configuration** (gear)
2. Click **Settings**
3. Find `[auth.anonymous]`
4. Set `enabled = false`
5. Save

### Add Authentication

```yaml
# docker-compose.yml
grafana:
  environment:
    - GF_AUTH_GENERIC_OAUTH_ENABLED=true
    - GF_AUTH_GENERIC_OAUTH_CLIENT_ID=your_client_id
    - GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET=your_client_secret
    - GF_AUTH_GENERIC_OAUTH_SCOPES=openid,profile,email
    - GF_AUTH_GENERIC_OAUTH_AUTH_URL=https://oauth-provider/authorize
    - GF_AUTH_GENERIC_OAUTH_TOKEN_URL=https://oauth-provider/token
```

---

## Performance Tips

1. **Limit time range in queries**: Use 5m-1h instead of 30d
2. **Use rate() instead of absolute values**: `rate(metric[5m])`
3. **Aggregate with by()**: `sum by (endpoint) (...)`
4. **Set appropriate refresh rates**: Don't use 5s for all panels
5. **Use dashboard variables**: For dynamic filtering

---

## Advanced Configuration

### Persistent Grafana Data

```yaml
grafana:
  volumes:
    - grafana_data:/var/lib/grafana

volumes:
  grafana_data:
```

### Grafana Provisioning (Auto-Setup)

Create `devops/grafana/provisioning/dashboards.yml`:
```yaml
apiVersion: 1
providers:
  - name: 'dashboards'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

Mount in docker-compose:
```yaml
volumes:
  - ./devops/grafana/provisioning:/etc/grafana/provisioning
  - ./devops/grafana/dashboards:/var/lib/grafana/dashboards
```

---

## Acceptance Criteria (AC6)

### ✅ Grafana dashboard JSON skeleton present

```
docs/observability/grafana-dashboard.json
```

### ✅ Can be imported into local Grafana instance

1. Open http://localhost:3000
2. Dashboards → Import
3. Upload `grafana-dashboard.json`
4. Select Prometheus datasource
5. Click Import
6. View at http://localhost:3000/d/iot-hub-alpha-observability

### ✅ Shows 5 basic panels

1. 📊 Request Rate (req/s)
2. 🚨 Error Rate (%)
3. ⚡ Request Latency (ms)
4. 📦 Celery Tasks
5. 📈 Request Distribution by Endpoint

---

## References

- [Grafana Documentation](https://grafana.com/docs/)
- [Grafana Dashboard Guide](https://grafana.com/docs/grafana/latest/dashboards/)
- [PromQL Queries](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Dashboard Examples](https://grafana.com/grafana/dashboards)

---

**AC6 Acceptance Criteria**: ✅ COMPLETE

All requirements met:
- [x] Grafana dashboard JSON skeleton present
- [x] Can be imported into Grafana
- [x] Shows basic monitoring panels
- [x] Connected to Prometheus data source
