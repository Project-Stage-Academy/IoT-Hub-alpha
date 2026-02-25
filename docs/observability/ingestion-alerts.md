# Ingestion Alerts (Task #34)

## Scope
This document describes Grafana alert rules for ingestion monitoring:
- throughput
- latency
- error rate
- buffer saturation
- no-data detection


## Data Sources
Alerts use Prometheus metrics from:
- `web:8000/metrics` (HTTP ingest metrics)
- `mqtt_adapter:9103/metrics`
- `db-writer:9102/metrics`

## Alert Rules

### 1) IngestionHighErrorRate
Query:
```promql
sum(rate(ingest_errors_total[5m])) / clamp_min(sum(rate(ingest_messages_total{stage="raw",status="accepted"}[5m])), 1)
```
Thresholds:
- warning: `> 0.02` for `5m`
- critical: `> 0.05` for `5m`

### 2) IngestionHighP95Latency
Query:
```promql
histogram_quantile(0.95, sum by (le) (rate(ingest_latency_seconds_bucket{stage="end_to_end"}[10m])))
```
Thresholds:
- warning: `> 2` seconds for `10m`
- critical: `> 5` seconds for `10m`

### 3) IngestionDLQRatioHigh
Query:
```promql
(sum(rate(ingest_messages_total{stage="dlq",status="accepted"}[5m])) or vector(0))
/
clamp_min((sum(rate(ingest_messages_total{stage="raw",status="accepted"}[5m])) or vector(0)), 1)
```
Thresholds:
- warning: `> 0.01` for `5m`
- critical: `> 0.03` for `5m`

### 4) IngestionBufferSaturation
Query:
```promql
max(buffer_fill_ratio{component="db_writer_buffer"})
```
Thresholds:
- warning: `> 0.85` for `5m`
- critical: `> 0.95` for `5m`

### 5) IngestionNoData
Query:
```promql
sum(rate(ingest_messages_total{stage="raw",status="accepted"}[5m]))
```
Thresholds:
- warning: `< 0.001` for `10m`
- critical: `< 0.001` for `20m`

## Grafana Configuration
Folder: `Ingestion`  
Evaluation group: `ingestion-1m`  
Labels:
- `component=ingestion`
- `severity=warning|critical`

No data handling:
- for `IngestionNoData_*`: `No data = Alerting`
- for other rules: `No data = Normal`

## Verification

### Generate normal traffic
```powershell
python -m simulator.run -r 0.2 -c 30 -d device1 -v -m mqtt
```

### Generate DLQ traffic
```powershell
1..5 | % { '{"schema_version":"1.0","value":2443}' | docker compose exec -T mosquitto mosquitto_pub -h mosquitto -p 1883 -t telemetry/SN-NOT-EXISTS-999 -l }
```

### Check metric series
```powershell
docker compose exec prometheus wget -qO- http://mqtt_adapter:9103/metrics | findstr ingest_
docker compose exec prometheus wget -qO- http://db-writer:9102/metrics | findstr /C:"ingest_messages_total{" /C:"ingest_errors_total{" /C:"ingest_latency_seconds_count{" /C:"buffer_fill_ratio{" /C:"kafka_consumer_lag{"
```

## Baseline Note
Thresholds are baseline v1 and should be tuned after 2-3 days of real traffic.
