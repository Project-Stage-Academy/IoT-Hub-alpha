# Security — Monolithic MVP (Initial Decisions)

This document records the initial security decisions for the monolithic MVP.

## TLS (External Endpoints)
- **Staging/demo/prod-like environments:** external HTTP endpoints **MUST** be served over **TLS**.
- **Local development:** plain HTTP is acceptable.
- TLS termination is handled by a reverse proxy / ingress (outside the app containers). Internal Docker network traffic is not TLS-protected in MVP.

## Authentication (JWT)
- API uses **JWT**:
  - Authorization: `Bearer <token>`
  - Access token: **60 min**
  - Refresh token: **10 days**

## Telemetry Ingest Endpoint

- The telemetry ingest endpoint does NOT require authentication.
- Device identity is validated using a dedicated HTTP header:
  `X-Device-SSN`.
- The backend MUST validate that the provided SSN exists in the `devices`
  table before processing the request body.
- Requests with a missing or unknown `X-Device-SSN` MUST be rejected
  before telemetry parsing or persistence.
- The SSN is NOT required to be present in the request body and MUST NOT
  be used as a source of device identity.

## Secrets Handling

### Docker Compose
- Secrets are provided via environment variables loaded from `.env`.
- `.env` **MUST NOT** be committed to version control.
- `.env.example` documents required variables without exposing secrets.

### CI (GitHub Actions)
- Secrets **MUST** be stored in GitHub Actions Secrets.
- Secrets are injected into workflows as environment variables.
- Secrets **MUST NOT** be hardcoded in workflow files or logs.

## Internal APT Repository Access
- The internal APT repository is a restricted resource.
- Access is limited to CI pipelines and authorized infrastructure nodes.
- Authentication is enforced using credentials or SSH keys stored as CI secrets.
- APT repository credentials **MUST NOT** be committed to the repository.

---

## MQTT Broker — Future Security Roadmap

The Mosquitto broker currently runs with `allow_anonymous true` and no
encryption.  The sections below describe the planned hardening measures for
production readiness.

### 1. Device Authentication

| Option | Description | When to use |
|--------|-------------|-------------|
| **mTLS (mutual TLS)** | Each device presents a unique X.509 client certificate signed by the project CA. The broker verifies the certificate chain before allowing the connection. | Preferred for fleets where devices can store private keys securely (TPM / secure element). |
| **JWT-based auth** | The device obtains a short-lived JWT from a provisioning service and presents it as the MQTT password. A Mosquitto auth plugin (e.g. `mosquitto-go-auth`) validates the token signature and claims. | Useful when devices can reach an HTTP token endpoint and certificate management is impractical. |

**Implementation notes:**

- TLS listener on port **8883** with `require_certificate true` and
  `use_identity_as_username true` (for mTLS).
- For JWT: integrate an auth plugin that validates `exp`, `iss`, `sub`
  (device serial) and audience claims.
- Rotate credentials / certificates via an automated provisioning pipeline.

### 2. Topic-Level Authorisation (Device Isolation)

Each device MUST only be able to publish and subscribe to its own topics.
An ACL policy enforces this:

```
# Service account — internal adapter (read-only)
user mqtt_adapter
topic read telemetry/#
topic read devices/+/status
topic read $SYS/broker/log/#

# Per-device rules (%u is replaced with the authenticated username)
pattern write telemetry/%u
pattern readwrite devices/%u/status
```

- Devices authenticate with `username = serial_number`.
- A device **cannot** publish to another device's telemetry subtopic.
- The `mqtt_adapter` service account has read-only access and is the sole
  Kafka bridge.

### 3. Client Session Limits

| Control | Setting | Purpose |
|---------|---------|---------|
| **Max connections** | `max_connections <N>` | Cap total broker connections to prevent resource exhaustion. |
| **Max inflight messages** | `max_inflight_messages 20` | Limit unacknowledged QoS 1/2 messages per client. |
| **Max queued messages** | `max_queued_messages 1000` | Bound the offline message queue per client. |
| **Max packet size** | `message_size_limit 8192` | Reject oversized payloads at the protocol level. |
| **Keep-alive enforcement** | `max_keepalive 120` | Disconnect idle clients that miss keep-alive. |
| **Unique client IDs** | `use_username_as_clientid true` | Prevent client-ID collisions; one session per device. |

### 4. Payload Security

- **Schema validation**: The Kafka consumer (downstream) validates every
  `telemetry.raw` envelope against a JSON Schema before further processing.
  Malformed payloads are sent to a dead-letter topic.
- **Size limit**: `message_size_limit` on the broker rejects excessively
  large payloads before they enter the pipeline.
- **Encoding**: All payloads MUST be valid UTF-8 JSON objects.  Binary or
  non-JSON messages are logged and discarded by the `mqtt_adapter`.
- **Sanitisation**: The downstream consumer strips or escapes any fields
  before database insertion to prevent injection attacks.

### 5. Abuse Protection (DDoS, Throttling, Rate Limits)

| Layer | Mechanism | Details |
|-------|-----------|---------|
| **Network** | Firewall / security group | Restrict port `8883` to known IP ranges or VPN. Block `1883` (plain TCP) in production. |
| **Broker** | `max_connections` | Hard cap on simultaneous MQTT connections. |
| **Broker** | Connection rate limit (plugin) | Use `mosquitto-go-auth` or a custom plugin to limit new connections per IP per minute. |
| **Application** | Per-device publish rate | The `mqtt_adapter` tracks messages per `serial_number` in a sliding window; excess messages are dropped and logged. |
| **Application** | Payload deduplication | Idempotency check based on `(serial_number, timestamp, hash)` to discard duplicate publishes. |
| **Infrastructure** | Load-balancer / API gateway | For the HTTP path, rate-limiting middleware (`RATE_LIMIT_DEVICE_COUNT` / `RATE_LIMIT_DEVICE_PERIOD`) is already in place. Mirror equivalent limits for MQTT at the broker or adapter level. |

### 6. Transport Encryption (TLS)

- **Production**: all MQTT traffic MUST use TLS (`listener 8883`).
- **Certificate management**: use Let's Encrypt or an internal CA; automate
  renewal via cert-manager or a cron job.
- **Minimum TLS version**: TLS 1.2 (prefer 1.3).
- **Plain TCP (`1883`)** MUST be disabled or restricted to the internal
  Docker network only.

### Implementation Priority

| Phase | Items |
|-------|-------|
| **Phase 1** (next sprint) | TLS on broker, `allow_anonymous false`, password-file auth for `mqtt_adapter` service account. |
| **Phase 2** | Per-device mTLS or JWT auth, ACL file with `pattern` rules. |
| **Phase 3** | Session limits, message-size cap, connection rate-limit plugin. |
| **Phase 4** | Per-device publish throttling in `mqtt_adapter`, payload deduplication, dead-letter topic. |
