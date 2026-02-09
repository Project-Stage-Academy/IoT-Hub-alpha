#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://iot-industry.redocly.app/_mock/openapi}"
JWT="${JWT:-skldjhfjklsdhbgjksdbgjksdf.123uji12ghka}"


if [[ -z "${JWT}" ]]; then
  echo "JWT is required. Set JWT env var (or disable security on mock endpoints)."
  exit 2
fi

request() {
  local method="$1"
  local url="$2"
  local name="$3"
  shift 3

  echo "➡️  ${name}"

  local body_file
  body_file="$(mktemp)"
  local status

  status="$(curl -sS -w "%{http_code}" -o "$body_file" \
    --connect-timeout 5 --max-time 20 \
    -X "$method" "$url" "$@")" || {
      echo "❌ ${name} — network failure"
      echo "URL: ${url}"
      echo "Response:"
      cat "$body_file" || true
      rm -f "$body_file" || true
      exit 1
    }

  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "❌ ${name} — HTTP ${status}"
    echo "URL: ${url}"
    echo "Response:"
    cat "$body_file" || true
    rm -f "$body_file" || true
    exit 1
  fi

  rm -f "$body_file"
}

auth=(-H "Authorization: Bearer ${JWT}")
json=(-H "Content-Type: application/json")

# Rules
request GET \
  "${BASE_URL}/rules?page=1&page_size=10" \
  "Rules: list" \
  "${auth[@]}"

request POST \
  "${BASE_URL}/rules" \
  "Rules: create" \
  "${auth[@]}" "${json[@]}" \
  -d '{"name":"Low Vibration Alert Lathe","description":"Alerts maintenance when vibration drops below expected operating range","condition":{"type":"leaf","operator":"gt","threshold":5,"window_seconds":15,"occurances":3},"action_config":[{"type":"notification","recipients":["test@test.com"],"template_id":5},{"type":"stop_machine","machine_id":"CNC-002"}],"is_enabled":true,"device_id":"a80031eb-189a-49d5-93ab-11bd465143e9"}'

request GET \
  "${BASE_URL}/rules/29e31015-4733-49f3-855a-ef7f30e6c147" \
  "Rules: get by id" \
  "${auth[@]}"

request PATCH \
  "${BASE_URL}/rules/29e31015-4733-49f3-855a-ef7f30e6c147" \
  "Rules: patch enabled" \
  "${auth[@]}" "${json[@]}" \
  -d '{"enabled":true}'

request DELETE \
  "${BASE_URL}/rules/29e31015-4733-49f3-855a-ef7f30e6c147" \
  "Rules: delete" \
  "${auth[@]}"

# Devices
request GET \
  "${BASE_URL}/devices?page=1&page_size=10" \
  "Devices: list" \
  "${auth[@]}"

request POST \
  "${BASE_URL}/devices" \
  "Devices: create" \
  "${auth[@]}" "${json[@]}" \
  -d '{"device_type_id":"7ca821df-4d26-4eb6-bd4f-426b6e2f08c8","name":"Sensor 1","serial_number":"SN-001","location":"Lab","status":"active"}'

request GET \
  "${BASE_URL}/devices/29e31015-4733-49f3-855a-ef7f30e6c147" \
  "Devices: get by id" \
  "${auth[@]}"

request PATCH \
  "${BASE_URL}/devices/29e31015-4733-49f3-855a-ef7f30e6c147" \
  "Devices: patch" \
  "${auth[@]}" "${json[@]}" \
  -d '{"device_type_id":"7ca821df-4d26-4eb6-bd4f-426b6e2f08c8","name":"Sensor 1","serial_number":"SN-001","location":"Lab","status":"inactive"}'

request DELETE \
  "${BASE_URL}/devices/29e31015-4733-49f3-855a-ef7f30e6c147" \
  "Devices: delete" \
  "${auth[@]}"

# Telemetry
request GET \
  "${BASE_URL}/telemetry?page=1&page_size=10&device_id=a1b2c3d4-e5f6-7890-1234-567890abcdef" \
  "Telemetry: list" \
  "${auth[@]}"

# NOTE: spec has `security: []` for POST /telemetry, so no Authorization header here (keep it that way)
request POST \
  "${BASE_URL}/telemetry" \
  "Telemetry: ingest" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: unique-client-request-id-123" \
  -H "X-Device-Serial-Number: SN123456" \
  -d '{"schema_version":"1.0","value":25.5}'

# Events
request GET \
  "${BASE_URL}/events?page=1&page_size=10&device_id=a1b2c3d4-e5f6-7890-1234-567890abcdef&rule_id=29e31015-4733-49f3-855a-ef7f30e6c147&severity=warning&acknowledged=true" \
  "Events: list" \
  "${auth[@]}"

request GET \
  "${BASE_URL}/events/321" \
  "Events: get by id" \
  "${auth[@]}"

request POST \
  "${BASE_URL}/events/321/ack" \
  "Events: ack" \
  "${auth[@]}"

request POST \
  "${BASE_URL}/events/321/resolve" \
  "Events: resolve" \
  "${auth[@]}"

echo "✅ Contract smoke passed"
