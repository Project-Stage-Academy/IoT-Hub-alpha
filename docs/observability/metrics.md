# Prometheus Metrics - Part 1: HTTP & Celery Task Instrumentation

## Overview

This implementation provides comprehensive Prometheus metrics for monitoring the IoT Hub Alpha application. Part 1 focuses on HTTP request metrics and Celery task instrumentation, with plans to extend to database and queue metrics in future parts.

### What's Implemented

- **HTTP Request Metrics**: Track all incoming requests with method, endpoint, status code, and latency
- **Celery Task Metrics**: Monitor task execution, success/failure rates, and duration
- **Prometheus Scraping**: Auto-discovery and scraping of metrics from Django application
- **Grafana Integration**: Pre-configured Prometheus data source for Grafana dashboards

## Quick Start

### Access Prometheus Dashboard

```bash
# Open Prometheus UI
http://localhost:9090

# Query example metrics
http://localhost:9090/api/v1/query?query=http_requests_total
```

### Access Metrics Endpoint

```bash
# View raw metrics in Prometheus format
curl http://localhost:8000/metrics/
```

### Start Monitoring Stack

```bash
# Start core services + monitoring (Prometheus + Grafana)
docker compose up -d db redis web worker prometheus grafana
```

## Available Metrics

### HTTP Request Metrics

#### `http_requests_total` (Counter)

Total number of HTTP requests processed.

**Labels**: `method`, `endpoint`, `status`

```prometheus
http_requests_total{endpoint="/metrics/",method="GET",status="200"} 10.0
http_requests_total{endpoint="/health/",method="GET",status="200"} 5.0
http_requests_total{endpoint="/",method="GET",status="200"} 2.0
```

**Example Queries**:
```prometheus
# Total requests by endpoint
sum by (endpoint) (http_requests_total)

# Request rate (requests per second, over 5 minutes)
rate(http_requests_total[5m])

# Requests by status code
sum by (status) (http_requests_total)

# 4xx errors
sum(http_requests_total{status=~"4.."})

# 5xx errors
sum(http_requests_total{status=~"5.."})
```

#### `http_request_duration_seconds` (Histogram)

HTTP request latency in seconds.

**Labels**: `method`, `endpoint`

**Buckets**: 0.01s, 0.05s, 0.1s, 0.5s, 1.0s, 2.5s, 5.0s

```prometheus
http_request_duration_seconds_bucket{endpoint="/metrics/",le="0.01",method="GET"} 8.0
http_request_duration_seconds_bucket{endpoint="/metrics/",le="0.05",method="GET"} 9.0
http_request_duration_seconds_bucket{endpoint="/metrics/",le="0.1",method="GET"} 9.0
```

**Example Queries**:
```prometheus
# Average request latency
rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m])

# P95 latency (95th percentile)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# P99 latency (99th percentile)
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))

# Average latency per endpoint
avg by (endpoint) (rate(http_request_duration_seconds_sum[5m])) / avg by (endpoint) (rate(http_request_duration_seconds_count[5m]))
```

### Celery Task Metrics

#### `celery_tasks_total` (Counter)

Total number of Celery tasks processed.

**Labels**: `task_name`, `status` (success|failure)

```prometheus
celery_tasks_total{status="success",task_name="my_task"} 100.0
celery_tasks_total{status="failure",task_name="my_task"} 5.0
```

**Example Queries**:
```prometheus
# Total succeeded tasks
sum(celery_tasks_total{status="success"})

# Total failed tasks
sum(celery_tasks_total{status="failure"})

# Success rate
sum(celery_tasks_total{status="success"}) / (sum(celery_tasks_total{status="success"}) + sum(celery_tasks_total{status="failure"}))

# Task failure rate per task
celery_tasks_total{status="failure"} / (celery_tasks_total{status="success"} + celery_tasks_total{status="failure"})
```

#### `celery_task_duration_seconds` (Histogram)

Celery task execution duration in seconds.

**Labels**: `task_name`

**Buckets**: 0.1s, 0.5s, 1.0s, 5.0s, 10.0s

```prometheus
celery_task_duration_seconds_bucket{le="0.1",task_name="my_task"} 50.0
celery_task_duration_seconds_bucket{le="0.5",task_name="my_task"} 95.0
celery_task_duration_seconds_bucket{le="1.0",task_name="my_task"} 98.0
```

**Example Queries**:
```prometheus
# Average task duration
rate(celery_task_duration_seconds_sum[5m]) / rate(celery_task_duration_seconds_count[5m])

# P95 task duration
histogram_quantile(0.95, rate(celery_task_duration_seconds_bucket[5m]))

# Average duration per task
avg by (task_name) (rate(celery_task_duration_seconds_sum[5m])) / avg by (task_name) (rate(celery_task_duration_seconds_count[5m]))
```

### Stub Metrics (For Future Implementation)

These metrics are defined but not yet actively tracked:

- `celery_queue_length` (Gauge): Number of tasks in Celery queue
- `django_db_connections_active` (Gauge): Number of active database connections

## Architecture

### Metrics Collection Flow

```
Request/Task → Middleware/Signal Handler → Prometheus Client → /metrics/ Endpoint
                                                                       ↓
                                                            Prometheus Scraper
                                                                       ↓
                                                            TSDB Storage & Query Engine
```

### Components

#### 1. Middleware Instrumentation (`backend/config/middleware.py`)

The `RequestContextMiddleware` automatically records metrics for every HTTP request:

```python
# Records start time, processes request, then records latency and count
REQUEST_LATENCY.labels(method=request.method, endpoint=request.path).observe(latency)
REQUEST_COUNT.labels(method=request.method, endpoint=request.path, status=response.status_code).inc()
```

#### 2. Celery Signal Handlers (`backend/config/celery.py`)

Signal handlers track Celery task lifecycle:

- **`task_prerun`**: Stores task start time
- **`task_postrun`**: Records success, increments counter, observes duration
- **`task_failure`**: Records failure event

#### 3. Metrics Definition (`backend/config/metrics.py`)

Central location for all metric definitions using `prometheus_client` library.

#### 4. Metrics Endpoint (`backend/apps/core/views.py`)

Exposes metrics at `/metrics/` endpoint:

```bash
curl http://localhost:8000/metrics/
```

Returns metrics in Prometheus text exposition format.

#### 5. Prometheus Configuration (`devops/prometheus.yml`)

Scrape jobs configured for:
- **Django application**: Scrapes `/metrics/` every 10 seconds
- **Prometheus itself**: Self-monitoring every 15 seconds

```yaml
scrape_configs:
  - job_name: 'django'
    scrape_interval: 10s
    metrics_path: '/metrics/'
    static_configs:
      - targets: ['web:8000']
```

#### 6. Docker Compose Integration

Prometheus service with monitoring profile:

```bash
# Start with monitoring enabled
docker compose --profile monitoring up

# Or explicitly
docker compose up prometheus
```

## Configuration

### Environment Variables

**`ALLOWED_HOSTS`** (`.env`)

Must include all hostnames that will scrape metrics. For Docker Compose:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,web,prometheus,grafana
```

The Django security middleware validates incoming host headers. Prometheus uses the hostname `web:8000` from inside the container network.

### Prometheus Settings

Edit `devops/prometheus.yml` to adjust:
- `scrape_interval`: How often to scrape (default: 15s global, 10s for Django)
- `evaluation_interval`: How often to evaluate rules (default: 15s)
- `retention`: How long to keep metrics (default: 15 days)

```yaml
global:
  scrape_interval: 15s        # Default scrape interval
  evaluation_interval: 15s    # Default evaluation interval
  external_labels:
    environment: local
    service: iot-hub
```

## Common Queries

### Dashboard Overview

```prometheus
# Request throughput (requests/min)
sum(rate(http_requests_total[1m])) * 60

# Error rate (%)
(sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))) * 100

# P95 latency (ms)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) * 1000

# Active Prometheus targets
count(up)

# Prometheus uptime (hours)
(time() - process_start_time_seconds) / 3600
```

### Troubleshooting

```prometheus
# Check if Django target is up
up{job="django"}

# Check scrape duration (should be <100ms)
scrape_duration_seconds{job="django"}

# Check for scrape errors
ALERTS{alertname=~"ScrapeErrors"}
```

## Testing

### Verify Metrics Collection

```bash
# Make a test request to generate metrics
curl http://localhost:8000/health/

# View collected metrics
curl http://localhost:8000/metrics/ | grep http_requests_total

# Expected output:
# http_requests_total{endpoint="/health/",method="GET",status="200"} 1.0
```

### Query via Prometheus API

```bash
# Query total requests
curl 'http://localhost:9090/api/v1/query?query=http_requests_total'

# Query request rate
curl 'http://localhost:9090/api/v1/query?query=rate(http_requests_total[5m])'

# Query by endpoint
curl 'http://localhost:9090/api/v1/query?query=sum%20by%20(endpoint)%20(http_requests_total)'
```

### Query via Prometheus UI

1. Navigate to http://localhost:9090
2. Click on "Graph" tab
3. Enter PromQL query in the search box
4. Click "Execute"

Examples:
- `http_requests_total` - All request counters
- `rate(http_requests_total[5m])` - Request rate over 5 minutes
- `http_request_duration_seconds_bucket` - Latency buckets
- `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` - P95 latency

## Next Steps (Part 2)

- Database connection pooling metrics
- Celery queue length tracking
- Grafana dashboard for visualization
- Health check improvements
- Comprehensive observability documentation

## Dependencies

- `prometheus-client==0.20.0`: Prometheus client library for Python
- `prometheus:v2.54.1`: Prometheus time-series database container
- `grafana:11.2.0`: Visualization layer (optional, for Part 2)

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [Histogram Quantiles](https://prometheus.io/docs/practices/histograms/)