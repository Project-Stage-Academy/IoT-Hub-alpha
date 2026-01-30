# Prometheus Setup & Configuration Guide

## Overview

This document describes the Prometheus configuration, setup process, and how to extend it for future monitoring needs.

## Docker Compose Integration

### Service Configuration

The Prometheus service is defined in `docker-compose.yml`:

```yaml
prometheus:
  image: prom/prometheus:v2.54.1
  container_name: iot_hub_prometheus
  profiles: ["monitoring"]  # Optional service, requires --profile flag
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
  volumes:
    - ./devops/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - prometheus_data:/prometheus
  ports:
    - "9090:9090"
  depends_on:
    - web
  networks:
    - iot_hub_net
```

### Starting Prometheus

```bash
# Option 1: Start with monitoring profile
docker compose --profile monitoring up

# Option 2: Start individually
docker compose up prometheus

# Option 3: Start all services including monitoring
docker compose up -d db redis web worker prometheus grafana
```

### Stopping Prometheus

```bash
# Stop all services
docker compose down

# Or stop just Prometheus
docker compose stop prometheus
```

## Configuration File: `devops/prometheus.yml`

### Global Settings

```yaml
global:
  scrape_interval: 15s           # Default interval for scraping targets
  evaluation_interval: 15s       # How often to evaluate rules
  external_labels:               # Labels added to all metrics
    environment: local
    service: iot-hub
```

**Adjustments**:
- Increase `scrape_interval` to reduce overhead in production (e.g., 30s)
- Decrease for faster metrics collection (e.g., 5s) - higher storage usage

### Scrape Jobs

#### Django Application Target

```yaml
scrape_configs:
  - job_name: 'django'
    scrape_interval: 10s         # Override global interval
    metrics_path: '/metrics/'    # Endpoint path
    static_configs:
      - targets: ['web:8000']    # Container hostname:port
        labels:
          instance: 'django-app'
```

**Important Notes**:
- `targets` uses container service name `web` (not localhost)
- `metrics_path` must match the Django URL route
- `scrape_interval` is shorter (10s) for responsive metrics

#### Prometheus Self-Monitoring

```yaml
  - job_name: 'prometheus'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
```

Allows Prometheus to scrape its own internal metrics (`scrape_duration_seconds`, `up`, etc.).

## Network & Hostname Resolution

### Docker Compose Networking

All services run on the custom bridge network `iot_hub_net`:

```yaml
networks:
  iot_hub_net:
    name: iot_hub_net
```

**Service Discovery**:
- Service names resolve to their container IP addresses
- `web:8000` resolves to the Django container's internal IP
- No external host access needed

### ALLOWED_HOSTS Configuration

Django validates the `Host` header to prevent Host Header Injection attacks. Prometheus sends `Host: web:8000`, so it must be allowed:

**`backend/config/settings/local.py`**:
```python
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "web"]
```

## Storage & Data Retention

### TSDB (Time Series Database)

Prometheus uses TSDB for efficient time-series storage:

```bash
docker compose exec prometheus ls -lah /prometheus
```

Default settings:
- **Retention**: 15 days
- **Storage**: `/prometheus` volume (persisted across restarts)

### Customizing Retention

Modify Prometheus command in `docker-compose.yml`:

```yaml
command:
  - '--config.file=/etc/prometheus/prometheus.yml'
  - '--storage.tsdb.path=/prometheus'
  - '--storage.tsdb.retention.time=30d'      # Keep 30 days
  - '--storage.tsdb.retention.size=50GB'     # Or max 50GB
```

### Clearing Data

```bash
# Stop Prometheus
docker compose stop prometheus

# Remove volume
docker volume rm iot_hub_prometheus_data

# Restart (starts with empty database)
docker compose up prometheus
```

## Debugging & Troubleshooting

### Check Prometheus Logs

```bash
# View logs
docker compose logs prometheus

# Follow logs (tail)
docker compose logs -f prometheus

# Last 50 lines with grep
docker compose logs prometheus | grep -i error
```

### Verify Django Metrics Endpoint

```bash
# From host machine
curl http://localhost:8000/metrics/

# From Prometheus container
docker compose exec prometheus wget -O- http://web:8000/metrics/

# Check response format
curl http://localhost:8000/metrics/ | head -20
```

### Check Scrape Status

```bash
# Via API
curl http://localhost:9090/api/v1/targets | python3 -m json.tool

# In UI: http://localhost:9090/targets
```

Look for:
- `health: up` = target is healthy
- `lastError: ""` = no errors
- `lastScrape` = recent timestamp

If `health: down`:
1. Check network connectivity: `docker compose exec prometheus ping web`
2. Check ALLOWED_HOSTS in Django settings
3. Check metrics endpoint: `curl http://localhost:8000/metrics/`
4. View Django logs: `docker compose logs web`

### Test Metrics Query

```bash
# Health check
curl http://localhost:9090/-/healthy

# Readiness check
curl http://localhost:9090/-/ready

# Sample query (API)
curl 'http://localhost:9090/api/v1/query?query=up'
```

## Advanced Configuration

### Adding New Scrape Jobs

To monitor additional services, add to `devops/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: redis-exporter:9121
```

Then restart Prometheus:
```bash
docker compose restart prometheus
```

### Custom Alerting Rules

Create `devops/prometheus-rules.yml`:

```yaml
groups:
  - name: application_rules
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
```

Add to `devops/prometheus.yml`:

```yaml
global:
  # ...

rule_files:
  - '/etc/prometheus/prometheus-rules.yml'

scrape_configs:
  # ...
```

### Service Discovery

For dynamic environments, use service discovery instead of static configs:

```yaml
scrape_configs:
  - job_name: 'kubernetes'
    kubernetes_sd_configs:
      - role: pod
```

## Performance Considerations

### Memory Usage

```bash
# Check Prometheus memory usage
docker stats iot_hub_prometheus
```

Typical memory usage:
- Idle: 50-100 MB
- Active scraping: 100-500 MB
- Depends on cardinality (number of unique label combinations)

### High Cardinality Issues

If memory grows rapidly, check for high cardinality metrics:

```promql
# Top 10 highest cardinality metrics
topk(10, count by (__name__) (
  count by (__name__, __value__) (
    prometheus_tsdb_metric_chunks_created_total
  )
))
```

Solutions:
- Use `metric_relabel_configs` to drop high-cardinality labels
- Increase `scrape_interval` to reduce data points
- Implement label cardinality limits

### CPU Usage

CPU usage is typically low (<5%). High usage indicates:
1. Too many scrape targets
2. Complex PromQL queries
3. Small scrape interval
4. High-cardinality metrics

## Security

### Network Isolation

Prometheus runs on internal Docker network, not exposed to host by default. To access:

```bash
# Forward port locally
docker compose port prometheus 9090
# or
curl http://localhost:9090  # Already exposed in docker-compose.yml
```

### Read-Only Config

Prometheus config is mounted read-only (`:ro`):

```yaml
volumes:
  - ./devops/prometheus.yml:/etc/prometheus/prometheus.yml:ro
```

Changes require restarting the container.

### Authentication (Future)

For production, add reverse proxy with authentication:

```yaml
prometheus:
  # ... existing config ...
  environment:
    - AUTH_USERNAME=admin
    - AUTH_PASSWORD=secure_password
```

## Maintenance

### Regular Backups

```bash
# Backup Prometheus data
docker run --rm -v iot_hub_prometheus_data:/data \
  -v $(pwd)/backups:/backup \
  busybox tar czf /backup/prometheus-backup.tar.gz -C /data .

# Restore from backup
docker run --rm -v iot_hub_prometheus_data:/data \
  -v $(pwd)/backups:/backup \
  busybox tar xzf /backup/prometheus-backup.tar.gz -C /data
```

### Monitor Prometheus Itself

Query Prometheus internal metrics:

```promql
# Scrape duration (should be <100ms)
scrape_duration_seconds{job="django"}

# Samples ingested per second
rate(prometheus_tsdb_symbol_table_size_bytes[5m])

# Queries per second
rate(prometheus_engine_query_duration_seconds_total[5m])
```

## Connecting to Grafana

Prometheus URL for Grafana:

```
http://prometheus:9090
```

(Uses internal container network)

External URL (from host):

```
http://localhost:9090
```

## References

- [Prometheus Configuration Docs](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Prometheus Command-line Flags](https://prometheus.io/docs/prometheus/latest/command-line/prometheus/)
- [PromQL Documentation](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Best Practices](https://prometheus.io/docs/practices/rules/)