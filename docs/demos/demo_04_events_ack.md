# Events: Rule Fired → Event → Acknowledge

## `1) Goal`
Show the full event lifecycle:

- Rules fire from telemetry
- Events are created
- Events are acknowledged (admin or API)

---

## `2) Steps`

### Step 1: Seed demo data
```bash
docker compose exec web python manage.py seed_data --file seed/seed_events_demo.json
```

### Step 2: Trigger rule processing (immediate)
```bash
docker compose exec web python manage.py run_process_telemetry --start 0 --batch-size 200 --no-record-cursor
```

### Step 3: Verify Events exist (Admin)
Open admin:
```
http://localhost:8000/admin/
```
Then check:
```
Events → list view
```

### Step 4: Acknowledge an Event (choose one)

#### Option A: Admin action
- Select one or more Events
- Action: `Acknowledge selected events`
- Click `Go`

#### Option B: API (if you have a token)
```bash
curl -X POST \
  -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8000/api/v1/events/<EVENT_ID>/ack/
```

### Step 5: Optional checks (export or webhook)

#### Export CSV for reporting
```bash
docker compose exec web python manage.py export_events --since 2026-02-08 --output exports/events_demo.csv
```

## `3) Expected Results`
- Events are created after Step 2
- Acknowledged events change `status` to `acknowledged`
- API returns the updated event payload
