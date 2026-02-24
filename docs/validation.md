# Documentation Validation Note
This document records the validation of the project documentation, who performed it, date, and any doc fixes applied.

---

# Security Onboarding Validation

## Context
This validation documents a single onboarding run to verify that
the security foundation documentation is sufficient for a new developer
to start the project safely.

## Validator
- Name: Ruslan Krishtal
- Date: 2026-01-29
- Environment: Windows 10, Docker Desktop

## Validation Steps

| Area | Result |
|----|----|
Local TLS (https://localhost) | ✅ Success |
Secrets via .env | ✅ Loaded correctly |
Secrets not committed | ✅ Verified |
JWT issuance | ✅ Stub only – documented in auth.md, no token issued yet
APT repo access control | ✅ Basic auth enforced |
Docs clarity | ✅ Minor fixes applied |

## Issues Found & Fixes

- Clarified APT repo basic-auth setup and password generation steps
- Added notes about ignoring `.htpasswd` in git
- Updated README examples to match actual ports and paths

## Conclusion
The security foundation is sufficient for local development onboarding.
A new developer can follow the docs and reach a working, secure setup
in under 15 minutes.
# Validation

Use this checklist to confirm the local Docker stack is healthy.
Prereq: stack is running (see `docs/dev-environment.md`).

## Checklist

- `docker compose ps` shows `db` and `web` healthy
- `curl http://localhost:8000/health/`
- `docker compose run --rm migrate` completes
- `scripts/logs.sh -f -s web` shows no obvious errors

## Last validated
  
- Cold start: `scripts/up.sh`
- Rebuild: `docker compose build --no-cache`
- Volume persistence: `scripts/down.sh` then `scripts/up.sh` and verify DB data remains

## Optional

- DIND demo: `scripts/dind-demo/README.md`

---

# Smoke Test Validation

## Validator
- Name: Oleksandr Kolesnikov
- Date: 2026-02-15
- Environment: macOS, Docker Desktop

## Preconditions

```bash
docker compose --profile monitoring up -d --build
```

## Validation Steps

### Infrastructure Checks

| Check | Command | Result   | Output |
|-------|---------|----------|--------|
| Health endpoint | `curl -sf http://localhost:8000/health/` | ✅ PASSED | <details><summary>View</summary>`ok`</details> |
| Metrics endpoint | `curl -sf http://localhost:8000/metrics/ \| grep http_requests_total` | ✅ PASSED | <details><summary>View</summary><pre>http_requests_total{endpoint="/health/",method="GET",status="200"} 402.0<br>http_requests_total{endpoint="/ready/",method="GET",status="200"} 401.0<br>http_requests_total{endpoint="/metrics/",method="GET",status="200"} 1205.0<br>http_requests_total{endpoint="/admin/",method="GET",status="302"} 1.0<br>http_requests_total{endpoint="/admin/login/",method="GET",status="200"} 1.0<br>http_requests_total{endpoint="/admin/login/",method="POST",status="302"} 1.0<br>http_requests_total{endpoint="/admin/",method="GET",status="200"} 4.0<br>http_requests_total{endpoint="/admin/telemetry/telemetry/",method="GET",status="200"} 2.0<br>http_requests_total{endpoint="/admin/jsi18n/",method="GET",status="200"} 6.0<br>http_requests_total{endpoint="/api/v1/telemetry/",method="POST",status="201"} 1.0<br>http_requests_total{endpoint="/admin/rules/rule/",method="GET",status="200"} 2.0<br>http_requests_total{endpoint="/admin/rules/rule/run-processor/",method="GET",status="302"} 1.0<br>http_requests_total{endpoint="/admin/events/event/",method="GET",status="200"} 1.0<br>http_requests_total{endpoint="/admin/events/event/1/change/",method="GET",status="200"} 1.0</pre></details> |
| Prometheus ready | `curl -sf http://localhost:9090/-/ready` | ✅ PASSED | <details><summary>View</summary>`Prometheus Server is Ready.`</details> |
| Grafana ready | `curl -sf http://localhost:3000/api/health` | ✅ PASSED | <details><summary>View</summary><pre>{"database": "ok", "version": "11.2.0", "commit": "2a88694fd3..."}</pre></details> |

### TimescaleDB Index Validation

| Check | Command | Result | Output |
|-------|---------|--------|--------|
| Index validation | `./scripts/validate_timeseries.sh` | ✅ PASSED (6/6) | <details><summary>View</summary><pre>=== TimescaleDB Index Validation ===<br><br>Loading test data...<br>Loaded test records<br><br>Using device_id: 0ad2beff-16c2-4da5-a9ac-34b2ab3068ce<br><br>=== Verifying Indexes Exist ===<br><br>Index: idx_telemetry_device_time... EXISTS<br>Index: idx_telemetry_payload_gin... EXISTS<br>Index: telemetry_timestamp_idx... EXISTS<br><br>=== Running EXPLAIN ANALYZE ===<br><br>Query: device + timestamp... PASS (uses index)<br>Query: timestamp range... PASS (uses index)<br>Query: JSONB payload... PASS (uses index)<br><br>=== Results: 6 passed, 0 failed ===<br>All index validations passed.</pre></details> |

### Core Flows

| Flow | Command/Method | Result | Output                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
|------|----------------|--------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Seed data (devices, rules, templates) | `docker compose exec web python manage.py seed_data --create_superuser` | ✅ PASSED | <details><summary>View</summary><pre>Superuser created<br>Seed summary<br>Devices - created: 8, updated: 0<br>Device Types - created: 6, updated: 0<br>Rules: created - 9, updated: 0<br>Notification templates - created: 5, updated: 0<br>Telemetry: created - 3, updated: 0</pre></details>                                                                                                                                                                                                                                                                                      |
| Telemetry ingestion | `python -m simulator.run -r 0 -c 1 -d device1 -v -m mqtt` | ✅ PASSED | <details><summary>View</summary><pre>Started runner... total tasks: 1<br>device1: code=0, expected=0 latency=0 ms<br>Run ended<br>Sent: 1, passed: 1, failed: 0, errors: 0<br>Pass rate = 100.0%, Ran for: 1.01 s</pre></details>                                                                                                                                                                                                                                                                                                                                                   |
| Rule event generation | Admin → Run processor | ✅ PASSED | <details><summary>View</summary><pre>1. Sent telemetry: python -m simulator.run -r 0 -c 1 -d device1 -v -m mqtt<br>   Pass rate = 100.0%<br><br>2. Triggered rule processor via Admin<br><br>3. Worker logs (docker logs iot_hub_worker --tail 20):<br>   - rule_fired: [160.52] leaf 100.0<br>   - Event 4 created for Rule 933b1749-...<br>   - Notification enqueued<br>   - Action: "Stop machine stub"<br><br>4. Sent telemetry again<br><br>5. Worker logs:<br>   - rule_fired again<br>   - "Event exists and is on cooldown" (duplicate prevention working)</pre></details> |
| Metrics visible | Prometheus + Grafana | ✅ PASSED | <details><summary>View</summary><pre>1. Prometheus (http://localhost:9090):<br>   Status → Targets: 2/2 UP<br><br>2. Grafana (http://localhost:3000):<br>   Dashboard "IoT Hub Alpha - Observability" displays graphs<br><br>3. App metrics endpoint:<br>   curl http://localhost:8000/metrics/ → http_requests_total visible</pre></details> |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

## Issues Found & Fixes

| Issue | Severity | Status | Fix |
|-------|----------|--------|-----|
| Duplicate timestamp index | P2 | Noted | Django model defines `idx_telemetry_timestamp`, but TimescaleDB auto-creates `telemetry_timestamp_idx` when creating hypertable. Consider removing the manual index from the model. |

## Scripts Used

- `docs/demos/run_smoke.sh`
- `scripts/validate_timeseries.sh`