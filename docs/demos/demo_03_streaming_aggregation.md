# Streaming Aggregation Verification Demo

## 1) Goal
This demo demonstrates real-time aggregation of telemetry data and verifies
that streaming aggregation results are calculated correctly.

Specifically, it validates:

- Correct aggregation of telemetry values over a time window
- Accuracy of computed statistics (`count`, `min`, `max`, `avg`)
- Correct behavior of the aggregation or metrics endpoint

---

## 2) Steps

### Step 1: Validate seed data (optional but recommended)

After setting up the Docker Compose stack, run:

```bash
docker compose exec web python manage.py seed_data --dry_run
```

Note:
This step validates seed JSON structure and cross-references without writing data to the database.

### Step 2: Seed the database
```
docker compose exec web python manage.py seed_data
```
This command seeds devices, device types, rules, and aggregation-related configuration into the database.

### Step 3: Start telemetry ingestion
Navigate to the simulator directory:

Run the simulator for a fixed amount of cycles:
```
python -m simulator.run -f demo3.json -r 0.5 -v -c 5
```
or from docker:
```
docker compose run --rm simulator -f demo3.json -r 0.5 -v -c 5
```
This command:

- Sends telemetry payloads from demo3.json

- Runs at a rate of 2 request per second

### Step 4: Query aggregation endpoint
After the simulator finishes, query the aggregation endpoint:

```http
GET /api/v1/telemetry/aggregate?device_id=TEMP-SN-002&window=30s
Authorization: Bearer <token>
```

Alternative, if metrics are exposed:
```http
GET /metrics
```

## 3) Expected Results
Aggregation endpoint validation

The aggregation response MUST contain:

- count equal to the number of ingested telemetry messages

- min equal to the minimum value sent during the run

- max equal to the maximum value sent during the run

- avg equal to the arithmetic mean of all values

All aggregated values MUST match the expected results derived from demo3.json.

If Prometheus-style metrics are exposed:

- Telemetry ingestion counters MUST increment by the expected number of messages

- Aggregation-related metrics MUST reflect the processed telemetry volume

- No unexpected metric resets or gaps MUST occur during the run

## 4) Expected Outcome

- The simulator MUST exit with exit code 0

- No "failed" or "error" messages should be printed

- Aggregation results MUST be consistent with ingested telemetry data

- Aggregation and/or metrics endpoints MUST reflect correct streaming behavior