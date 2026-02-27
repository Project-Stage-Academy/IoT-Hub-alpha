# Metrics Quick Reference

## Metric Cheat Sheet

### Key SLOs (Service Level Objectives)

| Component | Metric | Target | Alert Threshold |
|-----------|--------|--------|-----------------|
| Rule Eval | p95 latency | < 10ms | > 50ms |
| Event Create | p95 latency | < 50ms | > 100ms |
| Kafka Process | p95 latency | < 100ms | > 500ms |
| Action Dispatch | p95 latency | < 50ms | > 100ms |
| End-to-End | p99 latency | < 500ms | > 1000ms |
| Error Rate | Any | < 0.1% | > 1% |
| Cache Hit Rate | Evaluator | > 95% | < 90% |
| Kafka Lag | Consumer | < 100 msgs | > 1000 msgs |

---

## Query Templates

### Rule Evaluation Performance
```promql
# p95 latency across all rules
histogram_quantile(0.95, rate(rule_evaluation_duration_ms_bucket[5m]))

# Error rate
rate(rule_evaluation_errors_total[5m])

# Evaluation rate (rules/sec)
rate(rules_evaluated_total[5m])
```

### Event Performance
```promql
# Event creation rate (events/sec)
rate(events_created_total[5m])

# Cooldown skip rate
rate(events_cooldown_skipped_total[5m]) by (rule_id)

# Event creation p95 latency
histogram_quantile(0.95, rate(event_creation_duration_ms_bucket[5m]))
```

### Kafka Performance
```promql
# Message processing rate (msgs/sec)
rate(kafka_messages_processed_total[5m]) by (topic)

# Error rate
rate(kafka_messages_processed_total{status="error"}[5m]) by (topic)

# Consumer lag (messages behind)
kafka_consumer_lag_messages by (consumer_group)

# Processing latency p99
histogram_quantile(0.99, rate(kafka_message_processing_duration_ms_bucket[5m]))
```

### System Throughput
```promql
# Events created per second
events_created_per_second

# Telemetry points processed per second
telemetry_points_per_second

# Ratio (events / telemetry)
events_created_per_second / telemetry_points_per_second
```

### Cache Health
```promql
# Cache hit rate
avg(realtime_evaluator_cache_hit_rate)

# Devices with low hit rate
realtime_evaluator_cache_hit_rate < 90

# Total cached rules
sum(realtime_evaluator_rules_cached)
```

---

## Alert Rules

```yaml
# Critical Alerts
- HighErrorRate: rule_evaluation_errors_total rate > 0.01/sec
- HighLatency: p95 latency > threshold for > 5 min
- KafkaConsumerLag: lag > 1000 msgs for > 5 min
- ActionDispatchFailure: error rate > 5% for > 5 min

# Warning Alerts
- ElevatedLatency: p95 latency > SLO for > 5 min
- CacheMiss: hit rate < 90% for > 10 min
- CooldownSpike: skip rate > 10/sec for > 5 min
```

---

## Prometheus Endpoints

```
# Raw metrics (scrape target)
http://localhost:8000/metrics/

# Prometheus API
http://localhost:9090/api/v1/...

# Graph UI
http://localhost:9090/graph
```

---

## Grafana Dashboards

### Available Dashboards
- **Rule Engine Performance**: `uid=iot-rule-engine`
  - 16 panels covering all metrics
  - Filterable by rule_id and device_id
  - Time range selector (default: last 6 hours)

### Common Visualizations
- **Stat Panels**: Summary metrics (total counts)
- **Graph Panels**: Time-series with multiple queries
- **Heatmaps**: Distribution of latencies
- **Tables**: Sorted metric values

---

## Integration Checklist

```python
# In rule evaluation code
from apps.rules.services.metrics import track_rule_evaluation

with track_rule_evaluation(rule_id, device_id, "gt"):
    result = eval_rule(condition, telemetry_point)

# In event creation code
from apps.rules.services.metrics import track_event_creation

with track_event_creation(rule_id):
    event = Event.objects.create(...)

# In Kafka consumer code
from apps.rules.services.metrics import track_kafka_message_processing

with track_kafka_message_processing(topic, group):
    process_message(msg)

# In action dispatch code
from apps.rules.services.metrics import track_action_dispatch

with track_action_dispatch("notification"):
    dispatch_action(...)

# Record special events
from apps.rules.services.metrics import (
    record_cooldown_skipped,
    record_window_state_points,
    record_notification_enqueued,
)

record_cooldown_skipped(rule_id, device_id)
record_window_state_points(rule_id, device_id, count)
record_notification_enqueued(template_id, "email")
```

---

## Debugging Tips

### No Metrics?
```bash
# Check endpoint is working
curl http://localhost:8000/metrics/ | head -20

# Check Prometheus scrape
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Check in code
python manage.py shell
>>> from config.metrics import RULE_EVALUATION_DURATION_MS
>>> print(RULE_EVALUATION_DURATION_MS.collect())
```

### High Latency?
```promql
# Find slowest rules
topk(10, histogram_quantile(0.95, rate(rule_evaluation_duration_ms_bucket[5m])))

# Find slowest devices
topk(10, histogram_quantile(0.95, rate(kafka_message_processing_duration_ms_bucket[5m])))

# Find slowest operators
topk(5, histogram_quantile(0.95, rate(rule_evaluation_duration_ms_bucket[5m]))) by (operator)
```

### High Error Rate?
```promql
# Errors by type
increase(rule_evaluation_errors_total[5m]) by (error_type)

# Errors by rule
increase(rule_evaluation_errors_total[5m]) by (rule_id)

# Error timeline
rate(rule_evaluation_errors_total[1m])
```

---

## Performance Tuning

### If Rule Evaluation is Slow
- Check operator complexity (eq/ne slower than lt/gt)
- Profile window state cleanup (may have old points)
- Verify telemetry point parsing

### If Event Creation is Slow
- Check database load (disk I/O, locks)
- Verify indexes on Event table
- Monitor connection pool exhaustion

### If Kafka Processing is Slow
- Check broker health (lag growth)
- Monitor network latency
- Verify consumer group configuration

### If Cache Hit Rate is Low
- Rules may be changing frequently
- Device may have many different rules
- Consider adjusting cache size

---

## Files Reference

| File | Purpose |
|------|---------|
| `config/metrics.py` | Metric definitions (18 metrics) |
| `apps/rules/services/metrics.py` | Helper functions & context managers |
| `docs/METRICS_GUIDE.md` | Comprehensive documentation |
| `devops/grafana/provisioning/dashboards/rule-engine-metrics.json` | Grafana dashboard |
| `devops/prometheus.yml` | Prometheus configuration |

---

## Related Documents

- 📊 [Metrics Guide](METRICS_GUIDE.md) - Detailed documentation
- 📈 [Grafana Dashboard](../devops/grafana/provisioning/dashboards/rule-engine-metrics.json) - JSON dashboard
- ⚙️ [Prometheus Config](../devops/prometheus.yml) - Scrape configuration
- 🔧 [API Documentation](API.md) - Backend endpoints