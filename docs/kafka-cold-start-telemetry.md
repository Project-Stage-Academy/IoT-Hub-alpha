# Kafka Telemetry Quick Cold Start (UI-First)

This is the shortest path from zero to a working local Kafka telemetry flow:

- ingest from HTTP and MQTT
- publish into `telemetry.raw`
- route to `telemetry.clean` and `telemetry.dlq`
- verify everything in Kafka UI

Run commands from the repo root.

- For Docker lifecycle (`scripts/up.sh`, `scripts/down.sh`): use **WSL** or **Git Bash**.
- For one-off app commands (`docker compose exec/run`): PowerShell is fine too.

## 1. Configure `.env` for Kafka mode

```powershell
Copy-Item .env.example .env
```

```powershell
(Get-Content .env) `
  -replace '^TELEMETRY_PIPELINE_MODE=.*$', 'TELEMETRY_PIPELINE_MODE=kafka' `
  -replace '^TELEMETRY_PRODUCER_BACKEND=.*$', 'TELEMETRY_PRODUCER_BACKEND=kafka' `
| Set-Content .env
```

Verify:

```powershell
Select-String -Path .env -Pattern '^TELEMETRY_PIPELINE_MODE=|^TELEMETRY_PRODUCER_BACKEND='
```

Expected:

```text
TELEMETRY_PIPELINE_MODE=kafka
TELEMETRY_PRODUCER_BACKEND=kafka
```

## 2. True cold start

```bash
scripts/down.sh --volumes --remove-orphans
scripts/up.sh --profile kafka-ui
```

```powershell
docker compose run --rm migrate
docker compose exec web python manage.py seed_data
```

Check topic bootstrap:

```powershell
docker compose logs --no-log-prefix kafka-init
```

Expected topics:

- `telemetry.raw`
- `telemetry.clean`
- `telemetry.dlq`
- `event.topic`

## 3. Start the raw-to-clean/dlq router

Run in a separate terminal:

```powershell
docker compose exec web python manage.py kafka_db_writer_stub --group-id iot-hub-manual-$(Get-Date -Format yyyyMMddHHmmss)
```

Without this process, `clean` and `dlq` will not increase.

## 4. Open Kafka UI first

Open:

- `http://localhost:8080`

In **Topics**, watch these counters while testing:

- `telemetry.raw` should increase after HTTP/MQTT ingestion
- `telemetry.clean` should increase for valid events
- `telemetry.dlq` should increase for invalid events

## 5. Send test telemetry

### HTTP test (valid + invalid)

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" -X POST "http://localhost:8000/api/v1/telemetry/" `
  -H "Content-Type: application/json" `
  -H "X-Device-Serial-Number: TEMP-SN-002" `
  -d "{\"schema_version\":\"1.0\",\"value\":2443}"
```

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" -X POST "http://localhost:8000/api/v1/telemetry/" `
  -H "Content-Type: application/json" `
  -H "X-Device-Serial-Number: TEMP-SN-002" `
  -d "{\"schema_version\":\"9.9\",\"value\":2443}"
```

Both usually return `202`. The invalid one should later route to `dlq`.

### MQTT test (valid + invalid)

```powershell
docker compose exec mosquitto mosquitto_pub -h localhost -p 1883 -t telemetry/TEMP-SN-002 -m '{"schema_version":"1.0","value":2443}'
```

```powershell
docker compose exec mosquitto mosquitto_pub -h localhost -p 1883 -t telemetry/SN-NOT-EXISTS-999 -m '{"schema_version":"1.0","value":2443}'
```

Now refresh Kafka UI and confirm topic counters changed as expected.

## 6. Optional simulator run

```powershell
docker compose run --rm simulator -m http -f kafka_clean_dlq_test.json -c 1 -r 0.1 -v
docker compose run --rm simulator -m mqtt -f kafka_clean_dlq_test.json -c 1 -r 0.1 -v
```

## 7. Focused telemetry tests

```powershell
docker compose exec web pytest apps/telemetry/tests/test_producers.py apps/telemetry/tests/test_views.py apps/telemetry/tests/test_mqtt_adapter.py -q
```

## 8. Common issues

`telemetry.raw` increases but `clean/dlq` do not:

- `kafka_db_writer_stub` is not running
- restart it with a fresh `--group-id`

Kafka UI not reachable:

- stack started without profile
- run: `scripts/up.sh --profile kafka-ui`

`Network iot_hub_net is still in use` on shutdown:

```powershell
docker ps --filter network=iot_hub_net --format "table {{.Names}}\t{{.Status}}"
```

```bash
scripts/down.sh --volumes --remove-orphans
```

## 9. Stop and reset

Stop stack:

```bash
scripts/down.sh
```

Hard reset (cold state next run):

```bash
scripts/down.sh --volumes --remove-orphans
```
