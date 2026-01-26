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

### Step 4: Aquire JWT token
```
GET .../api/v1/auth/fake
```

will return a "fake" development-only JWT token.

### Step 5: Register Device
```
POST .../api/v1/devices
Authorization: Bearer <JWT_token>
```

send the following body:
```json
{
    "name": "Lathe #4 Vibration Sensor",
    "ssn": "VIB-SN-555",
    "status": "active",
    "location": "Workshop X, Machine ID: 22222",
    "device_type": "7a123004-f09d-4d69-b7ee-25fbe2cc75a7"
}
```

### Step 6: Start telemetry ingestion

Run the simulator:
```
python -m simulator.run -f demo1.json -r 0.5 -v
```

Or if docker compose is running:
```
docker compose run --rm simulator -f demo1.json -r 0.5 -v
```

This command:

- Sends telemetry payloads from demo1.json to the newly created device

- Runs at a rate of 2 requests per second

- Enables verbose output

---
## `3) Expected Results:`
- The simulator MUST exit with exit code 0

- No "failed" or "error" messages should be printed

- All telemetry messages should be handled properly by the API