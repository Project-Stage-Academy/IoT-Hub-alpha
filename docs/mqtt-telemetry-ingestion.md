# MQTT Telemetry Ingestion

## Overview

IoT Hub Alpha supports two parallel ingestion paths for telemetry data:

| Path | Entry point | Transport |
|------|-------------|-----------|
| **HTTP** | `POST /api/v1/telemetry/` | REST / JSON |
| **MQTT** | Mosquitto broker → `mqtt_adapter` | MQTT v5 / JSON |

Both paths publish raw payloads to a **`telemetry.raw`** topic via a
pluggable producer abstraction.  Validation and persistence are handled
downstream by a Kafka consumer (separate story).

```
Device ─── HTTP POST ──▶ TelemetryIngestView ──▶ producer.publish_raw() ──▶ telemetry.raw
Device ─── MQTT pub  ──▶ Mosquitto ──▶ mqtt_adapter ──▶ producer.publish_raw() ──▶ telemetry.raw
```

---

## Setup

### 1. Environment variables

Copy `.env.example` → `.env` and review the MQTT section:

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER_HOST` | `mosquitto` | Hostname inside Docker network |
| `MQTT_BROKER_PORT` | `1883` | Broker listener port |
| `MQTT_TOPIC` | `telemetry/#` | Wildcard topic the adapter subscribes to |
| `MQTT_QOS` | `1` | MQTT Quality of Service level |
| `MQTT_CONNECT_TIMEOUT` | `10` | Connection timeout in seconds |
| `TELEMETRY_PRODUCER_BACKEND` | `log` | `"log"` (stub) or `"kafka"` (future) |

### 2. Start services

```bash
docker compose up -d mosquitto mqtt_adapter
```

The `mqtt_adapter` Django management command connects to the broker,
subscribes to `telemetry/#` and `devices/+/status`, and runs in a
long-lived loop.

---

## Mosquitto Configuration

The broker configuration lives in `devops/mosquitto/mosquitto.conf`.

| Directive | Value | Purpose |
|-----------|-------|---------|
| `listener` | `1883` | Plain TCP listener on the default MQTT port |
| `allow_anonymous` | `true` | No authentication required (dev mode) |
| `connection_messages` | `true` | Log client connect / disconnect events |
| `persistence` | `true` | Persist retained messages and subscriptions |

> **Note:** Authentication, ACL, and TLS are intentionally disabled for the
> current development milestone.  See [`docs/security.md`](security.md) for
> the planned production hardening roadmap.

### Connection / Disconnect Handling

1. **Broker-level**: `connection_messages true` logs every connect/disconnect
   in container stdout.
2. **Application-level**: The `mqtt_adapter` subscribes to
   `devices/+/status`.  Devices are expected to:
   - Publish `"online"` to `devices/<serial>/status` on connect.
   - Set a **Last Will and Testament (LWT)** message of `"offline"` on the
     same topic so the broker notifies on ungraceful disconnect.
3. The adapter's `_handle_device_status()` method logs each status change
   with the device serial number.

---

## Producer Abstraction

The `producers.py` module provides a `TelemetryProducer` protocol:

```python
class TelemetryProducer(Protocol):
    def publish_raw(self, data: dict, source: str, serial_number: str) -> None: ...
    def close(self) -> None: ...
```

- **`LogProducer`** (current) — logs events to stdout.  No external
  dependencies.
- **`KafkaProducer`** (future) — implement and set
  `TELEMETRY_PRODUCER_BACKEND=kafka`.

The `build_raw_event()` helper wraps every payload in a canonical envelope:

```json
{
  "source": "mqtt",
  "serial_number": "TEMP-SN-002",
  "received_at": "2026-02-17T16:00:00+00:00",
  "raw_payload": { "schema_version": "1.0", "value": 2550 }
}
```

---

## Testing

```bash
# Run all telemetry tests
docker exec iot_hub_web pytest apps/telemetry/ -v

# Run only MQTT adapter tests
docker exec iot_hub_web pytest apps/telemetry/tests/test_mqtt_adapter.py -v

# Run only producer tests
docker exec iot_hub_web pytest apps/telemetry/tests/test_producers.py -v
```

### Manual MQTT test (from host with `mosquitto_pub`):

```bash
mosquitto_pub \
  -h localhost -p 1883 \
  -t "telemetry/TEMP-SN-001" \
  -m '{"schema_version":"1.0","value":2550}'
```

Check `mqtt_adapter` logs for the `telemetry.raw event (log-only)` entry.

---

## Security

Authentication and authorisation are **not enabled** in the current
development configuration.  For the full production security roadmap —
including device authentication (mTLS / JWT), per-topic ACLs, session
limits, payload validation, and abuse protection — see
[`docs/security.md`](security.md).
