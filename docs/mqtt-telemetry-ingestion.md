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

### 1. Generate Mosquitto passwords

The broker requires authentication.  Run the helper script **once** before
first `docker compose up`:

```bash
bash devops/mosquitto/generate_passwords.sh
```

This creates `devops/mosquitto/passwords` with hashed credentials for the
`mqtt_adapter` service account and several demo device accounts.

### 2. Environment variables

Copy `.env.example` → `.env` and review the MQTT section:

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER_HOST` | `mosquitto` | Hostname inside Docker network |
| `MQTT_BROKER_PORT` | `1883` | Broker listener port |
| `MQTT_TOPIC` | `telemetry/#` | Wildcard topic the adapter subscribes to |
| `MQTT_USERNAME` | `mqtt_adapter` | Service account username |
| `MQTT_PASSWORD` | `mqtt_adapter_secret` | Service account password |
| `MQTT_QOS` | `1` | MQTT Quality of Service level |
| `MQTT_USE_TLS` | `false` | Enable TLS (requires cert setup) |
| `MQTT_CONNECT_TIMEOUT` | `10` | Connection timeout in seconds |
| `TELEMETRY_PRODUCER_BACKEND` | `log` | `"log"` (stub) or `"kafka"` (future) |

### 3. Start services

```bash
docker compose up -d mosquitto mqtt_adapter
```

The `mqtt_adapter` Django management command connects to the broker,
subscribes to `telemetry/#` and `devices/+/status`, and runs in a
long-lived loop.

---

## Mosquitto Configuration

Configuration files live in `devops/mosquitto/`:

| File | Purpose |
|------|---------|
| `mosquitto.conf` | Main broker config (listener, auth, logging) |
| `acl` | Topic-level access control rules |
| `passwords` | Hashed credentials (generated, **not committed**) |
| `generate_passwords.sh` | Script to create the password file |

### Authentication

- `allow_anonymous false` — every client must authenticate.
- Credentials are stored in a `password_file` hashed by `mosquitto_passwd`.
- The `mqtt_adapter` service account authenticates with
  `MQTT_USERNAME` / `MQTT_PASSWORD` from `.env`.

### Access Control (ACL)

| Principal | Rule | Topics |
|-----------|------|--------|
| `mqtt_adapter` | read | `telemetry/#`, `devices/+/status`, `$SYS/broker/log/#` |
| Device (`%u`) | write | `telemetry/%u` (own serial only) |
| Device (`%u`) | readwrite | `devices/%u/status` (own status only) |

Devices authenticate with `username = serial_number`.  They can only
publish telemetry to their own subtopic, enforcing per-device isolation.

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

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Unauthenticated access | `allow_anonymous false` + password file |
| Topic hijacking | ACL restricts devices to `telemetry/<own-serial>` |
| Credential leakage | Passwords file is `.gitignore`'d; generated locally |
| Broker ↔ adapter transport | Internal Docker network; TLS available via `MQTT_USE_TLS` |
| HTTP header spoofing | `X-Device-Serial-Number` required; further auth at API gateway level |
| Payload integrity | Raw payloads are deep-copied into an envelope with metadata |

For production, additionally consider:
- Enabling TLS on the Mosquitto listener (`listener 8883` + certs).
- Using an external secrets manager for credentials.
- Rate-limiting MQTT connections per client ID.
- Enabling Mosquitto's dynamic security plugin for runtime credential management.

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
  -u "TEMP-SN-001" -P "device_pass_001" \
  -t "telemetry/TEMP-SN-001" \
  -m '{"schema_version":"1.0","value":2550}'
```

Check `mqtt_adapter` logs for the `telemetry.raw event (log-only)` entry.
