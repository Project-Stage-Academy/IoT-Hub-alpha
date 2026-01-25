# Rule threshold triggers and notification creation

## `1) Goal`
This demo demonstrates rule triggers and notification flow:

- Triggering rules based on configured threshold values
- Automatic creation of notifications
- Proper notification delivery handling

---

## `2) Steps`

### Step 1: Validate seed data (optional but recommended)

After setting up the Docker Compose stack, run:

```bash
docker compose exec web python manage.py seed_data --dry_run
```

Note:
This step is optional, but recommended. It validates the seed JSON structure and cross-references without writing data to the database.

### Step 2: Seed the database
```bash
docker compose exec web python manage.py seed_data
```

This command seeds devices, device types, rules, and notification templates into the database.

### Step 3: Start telemetry ingestion
Navigate to the simulator directory:

Run the simulator:
```
python -m simulator.run -f demo2.json -r 0.5 -v
```

This command:

- Sends telemetry payloads from demo2.json

- Runs at a rate of 2 requests per second

- Enables verbose output

---
## `3) Expected Results:`
- The simulator MUST exit with exit code 0

- No "failed" or "error" messages should be printed

- All telemetry messages should be processed successfully by the API

- 3 rules MUST be triggered

- The expected number of notifications MUST be generated

- Notification delivery attempts MUST be recorded in the
`notification_deliveries` database table