# Troubleshooting & Implementation Guide

## Common Issues & Solutions

### Issue 1: Prometheus Shows "HTTP 400 Bad Request" for Django Target

**Symptoms**:
- Prometheus Targets page shows: `health: down`
- `lastError: "server returned HTTP status 400 Bad Request"`
- Django logs show: `Invalid HTTP_HOST header: 'web:8000'`

**Root Cause**:
Django's `CommonMiddleware` validates the HTTP `Host` header against `ALLOWED_HOSTS` as a security measure to prevent Host Header Injection attacks. When Prometheus scrapes from inside the container network, it sends `Host: web:8000`, which must be explicitly allowed.

**Solution**:
Add `"web"` to `ALLOWED_HOSTS` in `backend/config/settings/local.py`:

```python
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "web"]
```

**Verification**:
```bash
# Check if Django now accepts the request
docker compose exec prometheus wget -O- http://web:8000/metrics/

# Should return HTTP/1.1 200 OK instead of 400
```

### Issue 2: Metrics Endpoint Returns Empty or Minimal Data

**Symptoms**:
- `/metrics/` returns only Python runtime metrics
- No `http_requests_total` or other custom metrics visible

**Root Cause**:
Custom metrics are only recorded when requests are processed through the middleware. If testing immediately after startup, no requests have been made yet (except the health check).

**Solution**:
1. Generate some requests:
   ```bash
   curl http://localhost:8000/
   curl http://localhost:8000/health/
   curl http://localhost:8000/metrics/
   ```

2. Wait a few seconds for Prometheus to scrape

3. Query metrics:
   ```bash
   curl http://localhost:8000/metrics/ | grep http_requests_total
   ```

**Expected Output**:
```
http_requests_total{endpoint="/",method="GET",status="200"} 1.0
http_requests_total{endpoint="/health/",method="GET",status="200"} 1.0
http_requests_total{endpoint="/metrics/",method="GET",status="200"} 3.0
```

### Issue 3: Prometheus Can't Connect to Django Target on Startup

**Symptoms**:
- Initial scrape failures after container restart
- Errors resolve after waiting 10-20 seconds
- Target eventually shows `health: up`

**Root Cause**:
Django container takes time to start up (migrations, static files, etc.). Prometheus may attempt scrape before Django is ready.

**Solution**:
Already handled by `depends_on: [web]` in docker-compose.yml. If issues persist:

```bash
# Wait for all services to be healthy
docker compose exec db pg_isready
docker compose exec web curl -f http://localhost:8000/health/

# Check Prometheus logs
docker compose logs prometheus | tail -20
```

### Issue 4: High Memory Usage in Prometheus

**Symptoms**:
- `docker stats` shows Prometheus using 500MB+
- Memory grows continuously
- Docker container gets killed (OOMKilled)

**Root Cause**:
High cardinality metrics - too many unique combinations of label values. Example:

```prometheus
http_requests_total{
  endpoint="/api/user/123",    # Each user ID becomes a unique label
  method="GET",
  status="200"
}
http_requests_total{
  endpoint="/api/user/456",    # New label combination
  method="GET",
  status="200"
}
```

**Solution**:
1. Identify high-cardinality metrics:
   ```bash
   docker compose exec prometheus \
     curl 'http://localhost:9090/api/v1/label/__name__/values' | \
     python3 -m json.tool
   ```

2. Drop or modify high-cardinality labels in `devops/prometheus.yml`:
   ```yaml
   scrape_configs:
     - job_name: 'django'
       metric_relabel_configs:
         # Drop individual user IDs from endpoint path
         - source_labels: [endpoint]
           regex: '/api/user/.*'
           target_label: endpoint
           replacement: '/api/user/{id}'
   ```

3. Reduce scrape frequency:
   ```yaml
   scrape_configs:
     - job_name: 'django'
       scrape_interval: 30s    # Increase from 10s
   ```

### Issue 5: Missing Celery Task Metrics

**Symptoms**:
- `celery_tasks_total` not appearing in metrics
- No `celery_task_duration_seconds` data

**Root Cause**:
Signal handlers in `backend/config/celery.py` are defined but no Celery tasks have been executed yet. Metrics only record when events occur.

**Solution**:
1. Create and run a Celery task (see Testing section below)

2. Verify signal handlers are connected:
   ```python
   # In Django shell
   from config.celery import app
   from celery import signals

   # Check if handlers are registered
   print(signals.task_postrun.receivers)
   ```

### Issue 6: Prometheus Scrape Timeout

**Symptoms**:
- Scrape duration > 10s
- `lastError: "context deadline exceeded"`
- Errors in Prometheus logs

**Root Cause**:
Django is slow or hanging during metrics generation. Likely causes:
1. Database queries in request lifecycle
2. Middleware processing delays
3. Django template rendering

**Solution**:
```bash
# Test metrics endpoint response time
time curl http://localhost:8000/metrics/

# Should complete in <100ms
```

If slow:
1. Check Django logs for errors: `docker compose logs web`
2. Check middleware order: ensure RequestContextMiddleware is early
3. Increase scrape timeout in `devops/prometheus.yml`:
   ```yaml
   scrape_configs:
     - job_name: 'django'
       scrape_timeout: 30s    # Increase from default 10s
   ```

## Implementation Details

### How Metrics Are Collected

#### HTTP Request Metrics Flow

```
1. Request arrives at Django
   ↓
2. RequestContextMiddleware.__call__() is invoked
   - Records: request.request_id, start_time
   ↓
3. Request processed (views, database, etc.)
   ↓
4. Middleware records metrics AFTER response is ready:
   - REQUEST_LATENCY.observe(latency)
   - REQUEST_COUNT.inc()
   ↓
5. Response returned to client
```

**Implementation Location**: `backend/config/middleware.py` (lines 35-65)

#### Celery Task Metrics Flow

```
1. Celery worker starts executing task
   ↓
2. task_prerun signal fired
   - Signal handler: task._start_time = time.time()
   ↓
3. Task executes business logic
   ↓
4a. If successful: task_postrun signal fired
    - CELERY_TASKS_TOTAL.inc(status="success")
    - CELERY_TASK_DURATION_SECONDS.observe(duration)

4b. If failed: task_failure signal fired
    - CELERY_TASKS_TOTAL.inc(status="failure")
```

**Implementation Location**: `backend/config/celery.py` (lines 14-52)

### Metric Types Reference

#### Counter
Monotonically increasing value. Example: `http_requests_total`

```python
from prometheus_client import Counter

REQUEST_COUNT = Counter(
    'http_requests_total',           # Metric name
    'Total HTTP requests',            # Description
    ['method', 'endpoint', 'status']  # Label names
)

# Usage: Increment by 1
REQUEST_COUNT.labels(method="GET", endpoint="/", status="200").inc()

# Usage: Increment by N
REQUEST_COUNT.labels(method="GET", endpoint="/", status="200").inc(5)
```

**Properties**:
- Always increases (never decreases)
- Good for: total requests, total errors, total bytes

#### Gauge
Can go up or down. Example: active connections

```python
from prometheus_client import Gauge

DB_CONNECTIONS = Gauge(
    'django_db_connections_active',
    'Number of active database connections',
    ['database']
)

# Usage: Set value
DB_CONNECTIONS.labels(database='default').set(5)

# Usage: Increment/Decrement
DB_CONNECTIONS.labels(database='default').inc()
DB_CONNECTIONS.labels(database='default').dec()
```

**Properties**:
- Can increase or decrease
- Good for: connections, memory, queue depth

#### Histogram
Tracks distribution of values (latency, size). Example: `http_request_duration_seconds`

```python
from prometheus_client import Histogram

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0)  # Latency buckets
)

# Usage: Observe a value
REQUEST_LATENCY.labels(method="GET", endpoint="/").observe(0.042)
```

**Properties**:
- Captures multiple buckets and summary statistics
- Auto-generates _bucket, _sum, _count series
- Good for: latencies, durations, sizes

### Adding New Metrics

#### Step 1: Define the Metric

Edit `backend/config/metrics.py`:

```python
from prometheus_client import Counter, Gauge, Histogram

# Your new metric
MY_CUSTOM_METRIC = Counter(
    'my_custom_metric_total',
    'Description of what this counts',
    ['label1', 'label2']
)
```

#### Step 2: Record Metric in Code

Option A - In middleware (for HTTP-related metrics):

```python
# backend/config/middleware.py
from .metrics import MY_CUSTOM_METRIC

class RequestContextMiddleware:
    def __call__(self, request):
        response = self.get_response(request)
        MY_CUSTOM_METRIC.labels(
            label1=request.method,
            label2=response.status_code
        ).inc()
        return response
```

Option B - In signal handlers (for Celery-related metrics):

```python
# backend/config/celery.py
@signals.task_postrun.connect
def my_task_handler(sender=None, **kwargs):
    from config.metrics import MY_CUSTOM_METRIC
    MY_CUSTOM_METRIC.labels(
        label1=sender.name,
        label2='completed'
    ).inc()
```

Option C - In views or services:

```python
# backend/apps/core/views.py
from config.metrics import MY_CUSTOM_METRIC

def my_view(request):
    MY_CUSTOM_METRIC.labels(
        label1='service',
        label2='api'
    ).inc()
    return HttpResponse("OK")
```

#### Step 3: Verify Metric Appears

```bash
# Make the metric happen (e.g., make a request)
curl http://localhost:8000/

# Check metrics endpoint
curl http://localhost:8000/metrics/ | grep my_custom_metric
```

### Label Design Best Practices

**Good Labels** (Low Cardinality):
```prometheus
endpoint="/api/users"          # Fixed set of routes
method="GET"                    # Fixed set: GET, POST, PUT, etc.
status="200"                    # Fixed set: 200, 400, 500, etc.
```

**Bad Labels** (High Cardinality):
```prometheus
user_id="12345"                 # Millions of unique values
request_id="abc-123-def-456"    # Random/unique per request
timestamp="1234567890"          # Continuous values
```

**Rule of Thumb**: If label can have >1000 unique values, reconsider the design.

### Testing Metrics

#### Unit Test Example

```python
# backend/tests/test_metrics.py
from config.metrics import REQUEST_COUNT, REQUEST_LATENCY
from prometheus_client import REGISTRY

def test_request_metrics():
    # Get initial count
    initial = REGISTRY.get_value(
        'http_requests_total',
        labels={'method': 'GET', 'endpoint': '/', 'status': '200'}
    ) or 0

    # Simulate request
    REQUEST_COUNT.labels(method='GET', endpoint='/', status='200').inc()

    # Verify
    final = REGISTRY.get_value(
        'http_requests_total',
        labels={'method': 'GET', 'endpoint': '/', 'status': '200'}
    )

    assert final == initial + 1
```

#### Integration Test Example

```python
from django.test import Client

def test_request_through_middleware():
    client = Client()

    # Make request
    response = client.get('/health/')

    # Check metrics endpoint
    metrics_response = client.get('/metrics/')
    metrics_text = metrics_response.content.decode('utf-8')

    # Verify metrics were recorded
    assert 'http_requests_total{endpoint="/health/"' in metrics_text
    assert 'http_request_duration_seconds_bucket{endpoint="/health/"' in metrics_text
```

## Monitoring Prometheus Itself

### Health Checks

```bash
# Liveness probe
curl http://localhost:9090/-/healthy

# Readiness probe
curl http://localhost:9090/-/ready
```

### Key Internal Metrics

```promql
# Prometheus uptime
(time() - process_start_time_seconds) / 3600

# Scrape success rate
(count(scrape_duration_seconds) - count(scrape_errors_total)) / count(scrape_duration_seconds)

# Average scrape duration
avg(scrape_duration_seconds)

# Samples ingested per second
rate(prometheus_tsdb_symbol_table_size_bytes[5m])

# Prometheus memory usage
process_resident_memory_bytes / 1024 / 1024  # in MB
```

## Performance Optimization

### Reduce Data Volume

```yaml
# In devops/prometheus.yml
scrape_configs:
  - job_name: 'django'
    # Drop unnecessary metrics
    metric_relabel_configs:
      - source_labels: [__name__]
        regex: 'python_.*'  # Drop all Python runtime metrics
        action: drop
```

### Optimize Query Performance

```promql
# SLOW: Processes all points in range
rate(http_requests_total[24h])

# FASTER: Use shorter time window
rate(http_requests_total[5m])

# SLOW: Multiple aggregations
sum(http_requests_total) / sum(http_requests_total{status="200"})

# FASTER: Single pass aggregation
sum(http_requests_total{status="200"}) / sum(http_requests_total)
```

## References

- [Prometheus Metric Types](https://prometheus.io/docs/concepts/metric_types/)
- [Best Practices for Instrumentation](https://prometheus.io/docs/practices/instrumentation/)
- [Exposition Format](https://prometheus.io/docs/instrumenting/exposition_formats/)
- [Client Library Best Practices](https://prometheus.io/docs/instrumenting/writing_clientlibraries/)