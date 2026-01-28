## Flaky Issues & Known Instabilities

This document lists known flaky or timing-sensitive behaviors that may affect demo execution.

These issues are non-deterministic and usually related to startup timing, async processing, or environment constraints rather than functional defects.

## General Notes (Applies to All Demos)

All demos assume a freshly started stack (docker compose up -d)

Some services (DB, web, workers) may take several seconds to become ready

Ingest endpoint is asyncronous and may not be processed instantly

CI / slower machines may amplify timing-related issues

Mitigation (general):

Prefer running demos after services report healthy

Re-run the demo once before assuming failure

Use smoke scripts to validate baseline system health first

## Demo 1 – Device Registration & Telemetry Ingestion
### Symptoms

- Simulator exits successfully, but telemetry is not visible immediately
- Initial HTTP requests may fail with connection errors
- First few telemetry messages may be dropped

### Likely Causes

- Backend API not fully started when simulator begins
- Database migrations still running
- Docker networking not fully initialized

### Mitigations

- Ensure seed_data completes before running the simulator
- Add a short delay (2–5 seconds) before starting the simulator
- Prefer using a /health endpoint check if available

### Expected Behavior

- After backend startup stabilizes, telemetry ingestion becomes consistent
- Re-running the simulator should succeed without changes

## Demo 2 – Rule Threshold Triggering & Notifications
### Symptoms

- Rule triggers intermittently or with delay
- Notification records appear later than expected
- First rule execution may not fire

### Likely Causes

- Rules are evaluated asynchronously
- Notification delivery may be handled by background workers
- Database transaction timing can delay visibility

### Mitigations

- Allow a short grace period (e.g. 3–10 seconds) after ingestion
- Verify rules exist before sending telemetry
- Re-run telemetry once if no notification appears

### Notes

This demo assumes eventual consistency, not immediate execution

Notification creation is the source of truth, not delivery side-effects (email, webhook)

## Demo 3 – Streaming Aggregation & Derived Metrics
### Symptoms

- Aggregated values do not immediately match expected results
- Partial aggregation results visible during execution
- Aggregation windows appear offset

### Likely Causes

- Time-based aggregation windows (sliding / tumbling)
- Clock drift between host and container
- First aggregation window may be incomplete

### Mitigations

- Run the simulator long enough to fully populate at least one window
- Validate results after the simulator completes
- Avoid validating exact timestamps; focus on value correctness

### Notes

This demo is inherently timing-sensitive

Minor variations in aggregation timing are expected and acceptable

## Simulator-Related Flakiness
### Symptoms

- Simulator exits before backend processes all messages
- Exit code is non-zero due to transient HTTP failures

### Likely Causes

- Backend temporarily unavailable
- Rate too high for local machine
- Network hiccups during container startup

### Mitigations

- Use conservative rates for demos (rate <= 0.5)
- Prefer deterministic --count over infinite mode
- Allow simulator retries where applicable

## Non-Issues (By Design)

The following are not considered bugs:

- Delayed notification appearance
- Aggregation results appearing after simulator completion
- Minor timing differences between runs
- First-run failures immediately after docker compose up