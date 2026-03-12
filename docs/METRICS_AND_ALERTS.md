# Metrics and Alerts Documentation

## Overview

Real-time monitoring system for telemetry ingestion pipeline using Prometheus alerts and Grafana dashboards.

## Metrics

### Ingestion Metrics

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `telemetry_ingested_total` | Counter | `source` (http, mqtt) | Total messages ingested via API |
| `kafka_messages_processed_total` | Counter | `topic`, `consumer_group` | Messages processed from Kafka |

### DLQ Metrics

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `telemetry_dlq_total` | Counter | `original_topic`, `error_reason` | Messages sent to Dead Letter Queue |

### Recording Metrics

Metrics are recorded at these points:
- **HTTP ingestion**: `apps/telemetry/views.py` after successful Kafka publish
- **MQTT ingestion**: `apps/telemetry/management/commands/mqtt_adapter.py` after successful publish
- **DLQ processing**: `apps/telemetry/management/commands/dlq_consumer.py` when consuming DLQ messages

## Alert Rules

### HighDLQErrorRate (WARNING)
- **Threshold**: Error rate > 5% over 15 minutes
- **Duration**: Fires after 1 minute in "pending" state
- **Severity**: Warning
- **Action**: Email notification to admin

### CriticalDLQErrorRate (CRITICAL)
- **Threshold**: Error rate > 10% over 15 minutes
- **Duration**: Fires after 1 minute in "pending" state
- **Severity**: Critical
- **Action**: Email notification to admin

**Error Rate Calculation**:
```
(DLQ messages in 15m) / (Raw messages processed in 15m) * 100
```

## Grafana Dashboard

**Name**: Telemetry Ingestion
**UID**: telemetry-ingestion
**Location**: http://localhost:3000/d/telemetry-ingestion

### Panels

1. **Telemetry Raw - Total Messages (15m)** - Gauge showing raw messages over 15 minutes
2. **Telemetry Raw - Message Rate** - Time series showing message rate per second
3. **Total Messages Ingested** - Gauge showing all ingested messages
4. **Total Messages - HTTP** - Gauge showing HTTP ingested messages
5. **Total Messages - MQTT** - Gauge showing MQTT ingested messages
6. **Telemetry DLQ - Total Messages (15m)** - Gauge showing DLQ messages over 15 minutes
7. **Total DLQ Messages** - Gauge showing all DLQ messages
8. **DLQ Error Rate (%)** - Gauge with color thresholds:
   - Green: < 5%
   - Yellow: 5-10%
   - Red: ≥ 10%

## Architecture

```
Prometheus Rules        AlertManager          Notifications
(Evaluates every 30s)   (Routes alerts)       (SMTP email)

Alert Rule  ──→  Pending (1m)  ──→  Firing  ──→  AlertManager  ──→  Email
                                                                      (localhost:25)
```

## Configuration Files

### `devops/prometheus-alerts.yml`
Prometheus alert rule definitions. Two alert rules: HighDLQErrorRate and CriticalDLQErrorRate.

### `devops/alertmanager.yml`
AlertManager configuration for email routing.

```yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'email'
  group_by: ['alertname']
  group_wait: 10s
  repeat_interval: 12h

receivers:
  - name: 'email'
    email_configs:
      - to: 'admin@iot-hub.local'
        smarthost: 'localhost:25'
```

### `devops/prometheus.yml`
Prometheus configuration with alert rules and AlertManager endpoint.

```yaml
alerting:
  alertmanagers:
    - targets: ['alertmanager:9093']

rule_files:
  - /etc/prometheus/prometheus-alerts.yml
```

### `docker-compose.yml`
AlertManager service configuration.

```yaml
alertmanager:
  image: prom/alertmanager:v0.26.0
  volumes:
    - ./devops/alertmanager.yml:/etc/alertmanager/config.yml:ro
  ports:
    - "9093:9093"
```

## Metrics Exposure

Each management command exposes metrics on a dedicated HTTP port:

| Service | Port | Command |
|---------|------|---------|
| Django | 8000/metrics/ | Web server |
| Rules Consumer | 9101 | `rules_consumer` |
| Events Consumer | 9102 | `events_consumer` |
| DB Writer | 9100 | `db_writer` |
| MQTT Adapter | 9103 | `mqtt_adapter` |
| DLQ Consumer | 9104 | `dlq_consumer` |

## Check Alert Status

### Via Prometheus API
```bash
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[0].rules[0]'
```

### Via AlertManager Web UI
```
http://localhost:9093
```

### Via AlertManager API
```bash
curl -s http://localhost:9093/api/v1/alerts | jq '.data[]'
```

### Check Error Rate
```bash
curl -s "http://localhost:9090/api/v1/query?query=<error_rate_expr>" | jq '.data.result[0].value[1]'
```

## Email Configuration

### Development (Default - Stub Mode)
Emails are logged to stdout instead of actually sent.

Check logs:
```bash
docker compose logs web | grep "STUB EMAIL"
```

### Production (Real Email)

Update `.env`:
```bash
SMTP_HOST=your-smtp-server
SMTP_PORT=587
SMTP_FROM=alerts@example.com
ADMIN_EMAIL=admin@example.com
```

Update `devops/alertmanager.yml`:
```yaml
receivers:
  - name: 'email'
    email_configs:
      - to: '{{ admin_email }}'
        from: '{{ smtp_from }}'
        smarthost: '{{ smtp_host }}:{{ smtp_port }}'
        auth_username: '{{ smtp_user }}'
        auth_password: '{{ smtp_password }}'
        require_tls: true
```

Restart AlertManager:
```bash
docker compose restart alertmanager
```

## Troubleshooting

### Alert Not Firing
1. Check Prometheus rules loaded:
   ```bash
   curl -s http://localhost:9090/api/v1/rules | jq '.data.groups'
   ```

2. Check error rate exceeds threshold:
   ```bash
   curl -s "http://localhost:9090/api/v1/query?query=..." | jq '.data.result[0].value[1]'
   ```

3. Verify AlertManager is running:
   ```bash
   docker compose ps | grep alertmanager
   ```

### No Email Sent
1. Check AlertManager status at `http://localhost:9093`
2. Check logs: `docker compose logs alertmanager`
3. Verify SMTP server accessible from container

### Metrics Not Appearing
1. Verify service exposes metrics on correct port
2. Check Prometheus scrape config: `http://localhost:9090/targets`
3. Restart service to expose metrics: `docker compose restart <service>`

## Testing

Run DLQ consumer tests:
```bash
docker compose exec web python manage.py test apps.telemetry.tests.test_dlq_consumer -v 2
```

## References

- Prometheus: http://localhost:9090
- AlertManager: http://localhost:9093
- Grafana: http://localhost:3000
- Dashboard: http://localhost:3000/d/telemetry-ingestion
