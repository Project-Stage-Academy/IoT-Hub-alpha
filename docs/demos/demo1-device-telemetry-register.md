# Device Registration and Telemetry Ingestion Demo

## `1) Goal`
This demo demonstrates the full telemetry ingestion flow:

- Seeding demo data using the `seed_data` management command
- Running the telemetry simulator
- Verifying successful API ingestion

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
```
cd simulator/
```
Run the simulator:
```
python run.py -f demo1.json -r 0.5 -v
```

This command:

- Sends telemetry payloads from demo1.json

- Runs at a rate of 2 requests per second

- Enables verbose output

---
## `3) Expected Results:`
- The simulator MUST exit with exit code 0

- No "failed" or "error" messages should be printed

- All telemetry messages should be handled properly by the API