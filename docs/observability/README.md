# Observability Guide - IoT Hub Alpha

Complete monitoring and observability documentation for the IoT Hub Alpha application.

## 📊 What's Included

This observability stack provides:

- **Structured JSON Logging**: All application and Celery logs in JSON format with context
- **Prometheus Metrics**: HTTP request metrics, Celery task metrics, and custom metrics
- **Grafana Dashboards**: Real-time visualization of metrics and system health
- **Health Checks**: Container liveness and readiness probes
- **Comprehensive Documentation**: Setup guides, troubleshooting, and examples

---

## 🚀 Quick Start

### Start Monitoring Stack (5 minutes)

```bash
# Start all services
docker compose up -d db redis web worker prometheus grafana

# Access dashboards
open http://localhost:3000  # Grafana
open http://localhost:9090  # Prometheus
open http://localhost:8000/metrics/  # Metrics endpoint
```

### Login to Grafana

```
URL:      http://localhost:3000
Username: admin
Password: admin
```

### View Dashboard

1. Open Grafana
2. Go to **Dashboards** → **Browse**
3. Click **IoT Hub Alpha - Observability**

---

## 📚 Documentation Index

### Part 1: Foundation (Logging & Metrics)

| Document | Purpose | Time |
|----------|---------|------|
| [**logging.md**](logging.md) | Structured JSON logs, querying, and analysis | 15 min |
| [**metrics.md**](metrics.md) | Complete metrics reference with PromQL queries | 20 min |
| [**prometheus-setup.md**](prometheus-setup.md) | Prometheus configuration and deployment | 15 min |
| [**troubleshooting.md**](troubleshooting.md) | Troubleshooting common issues and diagnostics | 30 min |

**Status**: ✅ Complete (Part 1: Logging & Metrics collection)

### Part 2: Visualization & Health

| Document | Purpose | Time |
|----------|---------|------|
| [**grafana-setup.md**](grafana-setup.md) | Grafana installation and configuration | 15 min |
| [**healthchecks.md**](healthchecks.md) | Container health checks and probes | 10 min |
| [**setup-guide.md**](setup-guide.md) | Complete setup and usage guide | 30 min |

**Status**: ✅ Complete (Part 2: Visualization & Health)

---

## 🎯 Common Tasks

### View Metrics in Prometheus

1. Open http://localhost:9090
2. Click **Graph** tab
3. Enter PromQL query, e.g.:
   ```promql
   http_requests_total
   rate(http_requests_total[5m])
   histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
   ```
4. Click **Execute** to see results

**See**: [metrics.md](metrics.md) for 50+ example queries

### View Metrics in Grafana

1. Open http://localhost:3000
2. Open dashboard: **IoT Hub Alpha - Observability**
3. 5 panels show:
   - 📊 Request rate (req/s)
   - 🚨 Error rate (%)
   - ⚡ Request latency (ms)
   - 📦 Celery tasks (success/failure)
   - 📈 Request distribution by endpoint

**See**: [grafana-setup.md](grafana-setup.md) for customization

### Monitor HTTP Requests

Check request performance and errors:

```promql
# Request rate (requests per second)
sum(rate(http_requests_total[5m]))

# Error rate (percentage)
(sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) * 100

# P95 latency (milliseconds)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) * 1000
```

**See**: [metrics.md](metrics.md) section "HTTP Request Metrics"

### Monitor Celery Tasks

Check background task health:

```promql
# Total tasks succeeded
sum(celery_tasks_total{status="success"})

# Total tasks failed
sum(celery_tasks_total{status="failure"})

# Task failure rate
sum(celery_tasks_total{status="failure"}) / (sum(celery_tasks_total{status="success"}) + sum(celery_tasks_total{status="failure"}))
```

**See**: [metrics.md](metrics.md) section "Celery Task Metrics"

### Add New Metric to Dashboard

1. Define metric in code: [setup-guide.md](setup-guide.md) → Part 3
2. Record metric in middleware/signals
3. Create PromQL query in Prometheus
4. Add panel to Grafana dashboard

**Step-by-step guide**: [setup-guide.md](setup-guide.md) → "Part 3: Adding New Metrics"

### Troubleshoot Issues

**Problem**: Dashboards show no data
→ See [troubleshooting.md](troubleshooting.md) → "Issue 2: Metrics Not Appearing"

**Problem**: Grafana can't connect to Prometheus
→ See [grafana-setup.md](grafana-setup.md) → "Issue 2: Data Source Connection Error"

**Problem**: Service shows unhealthy
→ See [healthchecks.md](healthchecks.md) → "Issue 1: Container Shows Unhealthy"

**More issues**: [troubleshooting.md](troubleshooting.md) has 10+ common problems

---

## 📋 What You Can Monitor

### Application Health

- **HTTP Requests**: Rate, latency, error rate by endpoint
- **Service Health**: Liveness checks, readiness checks
- **Response Times**: P50, P95, P99 latency percentiles
- **Errors**: 4xx client errors, 5xx server errors

### Background Jobs

- **Celery Tasks**: Success rate, failure rate, duration
- **Task Backlog**: Queue length, pending tasks
- **Job Performance**: Slow tasks, stuck tasks

### System Resources

- **CPU**: Process CPU time, container CPU limits
- **Memory**: Resident memory, virtual memory
- **Disk**: Data directory usage, log storage
- **Network**: Requests per second, bytes transferred

---

## 🔍 Understanding the Architecture

```
┌─ Application ─────────────────────────┐
│  Django + Celery (port 8000)          │
│  Generates metrics continuously       │
└──────────────┬────────────────────────┘
               │
        ┌──────▼──────┐
        │  /metrics/  │ (Prometheus text format)
        │  Endpoint   │
        └──────┬──────┘
               │
     ┌─────────▼─────────┐
     │  Prometheus       │ (port 9090)
     │  Scrapes metrics  │ (every 30s)
     │  Stores in TSDB   │ (15 day retention)
     └─────────┬─────────┘
               │
     ┌─────────▼─────────┐
     │  Grafana          │ (port 3000)
     │  Queries metrics  │ (real-time)
     │  Visualizes data  │ (5 dashboards)
     └───────────────────┘
```

**Details**: [prometheus-setup.md](prometheus-setup.md) → "Architecture" section

---

## ✅ Acceptance Criteria

### AC1: Structured JSON Logging ✅
```json
{"timestamp": "2026-01-27 13:30:00", "level": "INFO", "request_id": "abc-123", ...}
```
**See**: [logging.md](logging.md) - Structured logging reference

### AC2: /metrics Endpoint ✅
```
GET http://localhost:8000/metrics/
→ Returns Prometheus-format metrics
```
**See**: [metrics.md](metrics.md) - AC2 section

### AC3: Celery Metrics ✅
```
celery_tasks_total{task_name="...",status="success"} N
celery_task_duration_seconds{task_name="..."} N
```
**See**: [metrics.md](metrics.md) - AC3 section

### AC4: Prometheus Config ✅
```yaml
scrape_configs:
  - job_name: 'django'
    scrape_interval: 10s
    metrics_path: '/metrics/'
    targets: ['web:8000']
```
**See**: [prometheus-setup.md](prometheus-setup.md)

### AC5: Health Checks ✅
```bash
docker compose ps
# iot_hub_web  Up (healthy)
# iot_hub_db   Up (healthy)
```
**See**: [healthchecks.md](healthchecks.md)

### AC6: Grafana Dashboard ✅
```
docs/observability/grafana-dashboard.json
5 panels: request rate, error rate, latency, celery tasks, endpoints
```
**See**: [grafana-setup.md](grafana-setup.md)

### AC7: Documentation ✅
```
docs/observability/
├── metrics.md
├── prometheus-setup.md
├── grafana-setup.md
├── healthchecks.md
├── setup-guide.md ← Complete setup instructions
└── README.md ← You are here
```
**See**: [setup-guide.md](setup-guide.md)

### AC8: Troubleshooting ✅
```
Documented 10+ common issues with solutions
Diagnostic commands: curl, docker, prometheus queries
Support ticket collection script: collect-observability-data.sh
```
**See**: [troubleshooting.md](troubleshooting.md)

### AC9: CI Linting ✅
```bash
# Prometheus YAML validated with yamllint
yamllint devops/prometheus.yml

# Grafana JSON validated with jq
jq empty devops/grafana/provisioning/dashboards/grafana-dashboard.json
```
**See**: [.github/workflows/ci.yml](.github/workflows/ci.yml) - config-validation job

---

## 🎓 Learning Path

**New to monitoring?**
1. Start with [**Quick Start**](#-quick-start) above
2. Read [**setup-guide.md**](setup-guide.md) → Parts 1-2
3. Explore dashboard: http://localhost:3000
4. Try example queries in [**metrics.md**](metrics.md)

**Want to add metrics?**
1. Read [**setup-guide.md**](setup-guide.md) → Part 3
2. Choose metric type: Counter, Gauge, or Histogram
3. Add to code, record metrics, test in Prometheus
4. Add panel to Grafana dashboard

**Need to troubleshoot?**
1. Check [**troubleshooting.md**](troubleshooting.md) first
2. Check logs: `docker compose logs web prometheus grafana`
3. Use commands from [**logging.md**](logging.md) to query logs

**Going production?**
1. Review [**prometheus-setup.md**](prometheus-setup.md) → "Security" section
2. Configure persistent storage for Prometheus
3. Set up alerting rules
4. Configure backup strategy
5. Document team runbooks

---

## 📞 Support

### Quick Help

- **Dashboard not loading**: [troubleshooting.md](troubleshooting.md) → "Issue 3"
- **No data in panels**: [troubleshooting.md](troubleshooting.md) → "No Data in Panels"
- **Logs not appearing**: [logging.md](logging.md) → "Troubleshooting Log Issues"
- **Can't access Prometheus**: Check port 9090 is available

### Detailed Help

- **Complete metrics reference**: [metrics.md](metrics.md)
- **Prometheus configuration**: [prometheus-setup.md](prometheus-setup.md)
- **Grafana setup**: [grafana-setup.md](grafana-setup.md)
- **Health checks**: [healthchecks.md](healthchecks.md)

### Still Stuck?

1. Check all logs: `docker compose logs`
2. Verify services running: `docker compose ps`
3. Check logs with jq: See [logging.md](logging.md) for query examples
4. Review [troubleshooting.md](troubleshooting.md) for your specific issue

---

## 📦 Files Overview

```
docs/observability/
├── README.md                          ← Start here (this file)
├── logging.md                         ← Structured JSON logging & log queries
├── metrics.md                         ← Metrics reference + 50+ queries
├── prometheus-setup.md                ← Prometheus configuration
├── grafana-setup.md                   ← Grafana configuration
├── healthchecks.md                    ← Health checks documentation
├── setup-guide.md                     ← Complete setup walkthrough
├── troubleshooting.md                 ← Issue diagnosis & solutions
└── devops/grafana/provisioning/dashboards/grafana-dashboard.json ← Dashboard (import this)

backend/
├── config/metrics.py                  ← Metric definitions
├── config/middleware.py               ← Request metrics recording
├── config/celery.py                   ← Celery task metrics
├── apps/core/views.py                 ← Health check endpoints
└── scripts/healthcheck.sh             ← Health check script

devops/
└── prometheus.yml                     ← Prometheus scrape config

docker-compose.yml                     ← Service definitions
```

---

## 🚀 Next Steps

1. **[Get Started](#-quick-start)**: Follow quick start above
2. **[Learn More](#-learning-path)**: Read setup-guide.md
3. **[Explore Metrics](#monitor-http-requests)**: Try example queries
4. **[Customize Dashboard](#add-new-metric-to-dashboard)**: Add your metrics
5. **[Go Production](#going-production)**: Configure for production use

---

## 📈 Metrics at a Glance

| Metric | Type | Purpose | Query |
|--------|------|---------|-------|
| `http_requests_total` | Counter | HTTP requests | `sum(rate(...[5m]))` |
| `http_request_duration_seconds` | Histogram | Request latency | `histogram_quantile(0.95, ...)` |
| `celery_tasks_total` | Counter | Background tasks | `sum(...{status="success"})` |
| `celery_task_duration_seconds` | Histogram | Task duration | `histogram_quantile(0.95, ...)` |

**See**: [metrics.md](metrics.md) for complete reference

---

## 💡 Tips

- **Always make requests first**: Metrics won't appear without traffic
- **Wait 1-2 min for Prometheus**: Data takes time to accumulate
- **Use time picker**: Adjust Grafana time range when debugging
- **Check logs when stuck**: `docker compose logs -f web prometheus grafana`
- **Learn PromQL**: Understanding queries unlocks powerful monitoring

---

**Last Updated**: 2026-01-25
**Status**: ✅ All 9 Acceptance Criteria Complete
**Part 1**: ✅ Metrics & Logging
**Part 2**: ✅ Visualization & Health Checks

For detailed information, see specific guides above.
