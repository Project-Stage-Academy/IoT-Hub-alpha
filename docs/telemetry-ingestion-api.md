# Telemetry Ingestion API Guide

This guide documents real-time ingestion usage for integrators.
It focuses on the HTTP ingestion API only.

## Scope

- In scope: ingest API contract, request/response examples, setup and walkthrough.
- Out of scope: downstream consumer internals (clean telemetry services, analytics).

## Endpoint

- `POST /api/v1/telemetry/`

Base URL in local environment:

- `http://localhost:8000/api/v1/telemetry/`

## Request Contract

Headers:

- `Content-Type: application/json`
- `X-Device-Serial-Number: <registered-device-serial>` (required)
- `Idempotency-Key: <optional-client-key>` (optional)

Body (single object or array of objects):

- Required: `schema_version` (`"1.0"`)
- Optional: `value` (number or numeric string)
- Optional: `timestamp` (ISO 8601)

Notes:

- Device identity comes from `X-Device-Serial-Number`.
- If body contains `serial_number`, backend overwrites it with header value.
- If body contains `ssn`, backend removes it.
- For `schema_version=1.0`, backend normalizes `value` by dividing by `100`.

## Pipeline Modes

Configured by env vars:

- `TELEMETRY_PIPELINE_MODE=direct|kafka`
- `TELEMETRY_ASYNC_INGESTION=true|false` (used in `direct` mode)

Behavior:

- `direct + async=false`: validate + store in DB in request flow, returns `201`.
- `direct + async=true`: validate + queue Celery task, returns `202`.
- `kafka`: validate + publish raw event to Kafka topic, returns `202`.

## Setup Walkthrough

1. Start stack:

```bash
docker compose up -d --build
docker compose run --rm migrate
```

2. Ensure at least one registered device exists and note its serial number.

3. Set ingestion mode in `.env`:

```env
TELEMETRY_PIPELINE_MODE=direct
TELEMETRY_ASYNC_INGESTION=false
```

4. Send request examples below.

## Usage Examples

### 1) Single telemetry (temperature-like device)

`2550` means normalized `25.50` after `/100`.

```bash
curl -X POST "http://localhost:8000/api/v1/telemetry/" \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial-Number: TEMP-SN-002" \
  -d '{
    "schema_version": "1.0",
    "value": 2550
  }'
```

Typical direct-sync response (`201`):

```json
{
  "status": "created",
  "id": 12345,
  "device_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "timestamp": "2026-02-28T12:30:45.123456+00:00",
  "idempotency_key": "http:..."
}
```

### 2) Batch telemetry (vibration-like stream)

```bash
curl -X POST "http://localhost:8000/api/v1/telemetry/" \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial-Number: VIB-SN-001" \
  -H "Idempotency-Key: vib-batch-20260228-01" \
  -d '[
    {"schema_version": "1.0", "value": 1200},
    {"schema_version": "1.0", "value": "1230"}
  ]'
```

Typical batch response (`201` direct sync or `202` async/kafka depending mode).

### 3) Payload with source timestamp

```bash
curl -X POST "http://localhost:8000/api/v1/telemetry/" \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial-Number: TEMP-SN-002" \
  -d '{
    "schema_version": "1.0",
    "value": 2443,
    "timestamp": "2026-02-28T10:15:30Z"
  }'
```

### 4) Common validation errors

Missing required header:

```json
{
  "error": "X-Device-Serial-Number header is required"
}
```

Missing `schema_version`:

```json
{
  "error": "Validation failed",
  "details": {
    "schema_version": ["This field is required."]
  }
}
```

Invalid numeric `value`:

```json
{
  "error": "Validation failed",
  "details": {
    "value": ["Invalid numeric value provided."]
  }
}
```

## Response Codes

- `201`: created (direct sync mode).
- `202`: accepted (direct async or kafka mode).
- `400`: request/validation error.
- `409`: idempotency conflict in direct sync mode.
- `500`: internal processing error.
- `503`: temporary upstream issue (for example Kafka publish failure).

## Mock Server for Integration Testing

Hardware and frontend developers can test API integration locally using a mock server based on our OpenAPI specification. Since the project uses Docker, you can run the mock server instantly without installing any language-specific dependencies.

Run the mock server via Docker (from the repository root):

```bash
docker run --init --rm -p 4010:4010 -v "${PWD}/docs/api.yaml:/api.yaml" stoplight/prism:5 mock -h 0.0.0.0 /api.yaml

```

**Note for Windows users:** If you are using the standard Command Prompt (CMD), use `%cd%` instead of `${PWD}`:
```bash
docker run --init --rm -p 4010:4010 -v "%cd%/docs/api.yaml:/api.yaml" stoplight/prism:5 mock -h 0.0.0.0 /api.yaml
```

The server will start on port 4010. You can now send test requests to it:

```bash
curl -X POST "[http://127.0.0.1:4010/api/v1/telemetry](http://127.0.0.1:4010/api/v1/telemetry)" \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial-Number: MOCK-SN-001" \
  -d '{
    "schema_version": "1.0",
    "value": 1500
  }'
```

## Source of Truth

- OpenAPI contract: `docs/api.yaml`
- Ingestion implementation: `backend/apps/telemetry/views.py`
