## 1) Overview

This document explains and showcases demo scenarios, data seeding, and simulator usage.
It serves as a practical playbook for preparing, running, and troubleshooting demos.

---

## 2) Data Seeding

Data seeding provides a consistent initial state for demos and simulations.

- Seed data is loaded from  
  `/backend/seed/seed_data.json`
- The `seed_data` command inserts or updates database records in an **idempotent** manner
- Re-running the command is safe and will not create duplicate records

This ensures a predictable baseline before each demo.

---

## 3) Usage

### 3.1 Run data seeding

Data seeding can be initiated with:

```bash
docker compose exec web python manage.py seed_data
```

Supported CLI flags:
| flag | description |
|------|-------------|
|--flush| DANGER: Completely flushes the database and then seeds data|
|--flush_only| DANGER: Completely flushes the database without seeding|
|--force| Required confirmation flag for `--flush` and `--flush_only`|
|--dry_run| Validates JSON structure and foreign key references without writing to the database|
|--create_superuser| Seeds a superuser using email/password from environment variables|


Important notes:

- `--flush` and `--flush_only` require `--force`
- Flush operations are only allowed when `settings.DEBUG = True`

## 4) Pre-Demo Checks

Before running any demo scenario, verify the following:

- Docker Compose stack is running
- Database service is healthy and reachable
- Seed data validates successfully:
```bash
docker compose exec web python manage.py seed_data --dry_run
```
- Simulator configuration files (simulator/assets/demos/demo*.json) are present and valid

- API endpoints are reachable (optional sanity check via Postman or curl)

## 5) Resetting Data Between Demos

To reset the system to a clean, known state between demos:
```bash
docker compose exec web python manage.py seed_data --flush --force
```

This will:

- Remove all existing database records
- Re-seed the database with the default demo data

Warning:
This operation deletes all existing data and should only be used in development or demo environments.

## 6) Demos and simulator docs
Current available demos:
- [Demo 1 - Device telemetry registration](./demo_01_device_telemetry_register.md)
- [Demo 2 - Rule triggering and notification handling](./demo_02_rules_notifications.md)
- [Demo 3 - Telemetry streaming aggregation](./demo_03_streaming_aggregation.md)

[In-depth simulator documentation](../simulator.md)
## 7) Troubleshooting

### 7.1 Seed command fails

- Run with --dry_run to identify schema or reference issues
- Check that seed_data.json has no duplicate identifiers
- Ensure all referenced device types and devices exist

### 7.2 Simulator exits with non-zero exit code

- Inspect simulator output for "failed" or "error" messages

Verify that:

- Devices are seeded
- Device serial numbers match those in simulator payloads
- The API is reachable from the simulator container/host

### 7.3 Database-related issues
```bash
docker compose logs db
```
- Ensure migrations have been applied

- Restart the stack if connections appear stale:
```bash
docker compose down
docker compose up -d
```

### 7.4 Telemetry not appearing

- Confirm X-Device-Serial-Number header is sent by the simulator
- Verify device status is active
- Check API logs for validation or rule evaluation errors

## 8) Notes

- All demos assume a clean, seeded database
- Simulator success is determined by exit code equals 0
- Any non-zero exit code should be treated as a demo failure