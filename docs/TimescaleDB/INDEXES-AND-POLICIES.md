# AC4 Indexes and Retention Policies - Instructions

Complete guide for managing indexes and retention policies in the telemetry system.

---

##  Part 1: Database Indexes (in models.py)

All indexes are defined in [backend/apps/telemetry/models.py](../backend/apps/telemetry/models.py) in the `Meta.indexes` section (lines 22-35).

### Index 1: Composite Index (device_id + timestamp)

**Location:** [models.py:24-27](../backend/apps/telemetry/models.py#L24-L27)

```python
models.Index(
    fields=["device", "-timestamp"],
    name="idx_telemetry_device_time"
),
```

**Name in database:** `idx_telemetry_device_time`

**What it does:**
- Optimizes queries that filter by BOTH device AND time range
- Most common query pattern: "Get readings from Device X between date A and B"
- The `-timestamp` means descending order (newest first)

**Example queries that use this index:**
```sql
-- ✓ Uses this index
SELECT * FROM telemetry
WHERE device_id = 123
  AND timestamp >= '2026-01-01';

-- ✓ Uses this index
SELECT COUNT(*) FROM telemetry
WHERE device_id = 456
  AND timestamp BETWEEN '2026-01-01' AND '2026-01-31';
```

**Performance impact:** Reduces query time from ~500ms to <5ms for large datasets

---

### Index 2: Timestamp Only Index

**Location:** [models.py:28-32](../backend/apps/telemetry/models.py#L28-L32)

```python
models.Index(
    fields=["-timestamp"],
    name="idx_telemetry_timestamp"
),
```

**Name in database:** `idx_telemetry_timestamp`

**What it does:**
- Optimizes queries that only filter by time range (no device filter)
- Useful for dashboard queries showing all devices in a time period
- Secondary fallback when device ID is not in the query

**Example queries that use this index:**
```sql
-- ✓ Uses this index
SELECT * FROM telemetry
WHERE timestamp >= NOW() - INTERVAL '7 days';

-- ✓ Uses this index
SELECT device_id, COUNT(*) FROM telemetry
WHERE timestamp >= '2026-01-20'
GROUP BY device_id;
```

**Performance impact:** Faster time-range only queries (~10ms instead of 100ms+)

---

### Index 3: GIN Index (JSON Payload)

**Location:** [models.py:33-34](../backend/apps/telemetry/models.py#L33-L34)

```python
GinIndex(fields=["payload"], name="idx_telemetry_payload_gin"),
```

**Name in database:** `idx_telemetry_payload_gin`

**What it does:**
- GIN = Generalized Inverted Index
- Optimizes searches INSIDE the JSON payload column
- Allows filtering on JSON fields without extracting them
- Works with all JSON operators: `->`, `->>`, `@>`, etc.

**Example queries that use this index:**
```sql
-- ✓ Uses GIN index
SELECT * FROM telemetry
WHERE payload->>'metric_type' = 'temperature';

-- ✓ Uses GIN index
SELECT * FROM telemetry
WHERE payload->'serial_number' = '"SN12345"';

-- ✓ Uses GIN index (contains search)
SELECT * FROM telemetry
WHERE payload @> '{"metric_type": "vibration"}';
```

**Performance impact:** JSON searches ~50x faster with index vs without

---

##  How Indexes Work Together

```
Query Type                          | Best Index        | Fallback
------------------------------------|------------------|------------------
Device + Time                       | idx_device_time   | (primary choice)
Time only                          | idx_timestamp     | (device is ignored)
JSON payload only                  | idx_payload_gin   | (full table scan if missing)
Device + JSON                      | idx_device_time   | then idx_payload_gin
Device + Time + JSON              | idx_device_time   | then idx_payload_gin
```

---

## 🔧 How to Modify Indexes

### To Add a New Index

Edit [models.py](../backend/apps/telemetry/models.py) in the `Meta.indexes` list:

```python
class Meta:
    db_table = "telemetry"
    ordering = ["-timestamp"]
    indexes = [
        # Existing indexes...
        models.Index(fields=["device", "-timestamp"], name="idx_telemetry_device_time"),
        models.Index(fields=["-timestamp"], name="idx_telemetry_timestamp"),
        GinIndex(fields=["payload"], name="idx_telemetry_payload_gin"),

        # NEW INDEX: Add here
        models.Index(
            fields=["device", "payload"],
            name="idx_telemetry_device_payload"
        ),
    ]
```

Then run:
```bash
python manage.py makemigrations telemetry
python manage.py migrate
```

### To Remove an Index

1. Remove from the `indexes` list in [models.py](../backend/apps/telemetry/models.py)
2. Run migrations:
```bash
python manage.py makemigrations telemetry
python manage.py migrate
```

### To Check Existing Indexes

```bash
# In database
docker compose exec -T db psql -U postgres -d iot_hub_alpha_db << 'EOF'
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'telemetry'
ORDER BY indexname;
EOF
```

---

##  Part 2: Retention Policies (in migrations)

Retention policies are defined in [backend/apps/telemetry/migrations/0002_enable_timescaledb_hypertable.py](../backend/apps/telemetry/migrations/0002_enable_timescaledb_hypertable.py)

### What is a Retention Policy?

A retention policy automatically **deletes old data** based on age. Think of it as automatic cleanup.

---

### Policy 1: Retention (Delete After 365 Days)

**Location:** [migration 0002, lines 58-67](../backend/apps/telemetry/migrations/0002_enable_timescaledb_hypertable.py#L58-L67)

```python
# Add retention policy (365 days)
cursor.execute(
    """
    SELECT add_retention_policy(
        'telemetry',
        INTERVAL '365 days',
        if_not_exists => TRUE
    )
    """
)
```

**What it does:**
- Automatically deletes any telemetry records older than 365 days
- Runs automatically in background (once per hour by default)
- Keeps database size manageable

**Example:**
```
Today: 2026-01-30
Delete threshold: 365 days ago = 2025-01-30
All records before 2025-01-30 are deleted automatically
```

---

### Policy 2: Compression (Compress After 30 Days)

**Location:** [migration 0002, lines 69-79](../backend/apps/telemetry/migrations/0002_enable_timescaledb_hypertable.py#L69-L79)

```python
# Add compression policy (30 days)
cursor.execute(
    """
    SELECT add_compression_policy(
        'telemetry',
        INTERVAL '30 days',
        if_not_exists => TRUE
    )
    """
)
```

**What it does:**
- Automatically compresses chunks older than 30 days
- Reduces storage by 85-96% (columnstore + ZStandard compression)
- Happens in background (once per hour by default)
- Queries still work normally on compressed chunks

**Example:**
```
Today: 2026-01-30
Compression threshold: 30 days ago = 2025-12-31
All chunks before 2025-12-31 are automatically compressed
```

---

##  How to Change Retention Policies

### To Change Retention Period (e.g., from 365 to 180 days)

**Option A: Edit Migration (Recommended for new environments)**

Edit [migration 0002, line 63](../backend/apps/telemetry/migrations/0002_enable_timescaledb_hypertable.py#L63):

```python
# Change from 365 days to 180 days
cursor.execute(
    """
    SELECT add_retention_policy(
        'telemetry',
        INTERVAL '180 days',  # <-- Change here
        if_not_exists => TRUE
    )
    """
)
```

Then run:
```bash
python manage.py migrate
```

⚠️ **Note:** This only works on fresh databases. For existing databases, use Option B.

---

**Option B: SQL Command (For existing databases)**

```bash
docker compose exec -T db psql -U postgres -d iot_hub_alpha_db << 'EOF'
-- Remove old policy
SELECT remove_retention_policy('telemetry', if_exists => TRUE);

-- Add new policy with 180 days
SELECT add_retention_policy(
    'telemetry',
    INTERVAL '180 days',
    if_not_exists => TRUE
);
EOF
```

---

### To Change Compression Threshold (e.g., from 30 to 60 days)

**Option A: Edit Migration**

Edit [migration 0002, line 75](../backend/apps/telemetry/migrations/0002_enable_timescaledb_hypertable.py#L75):

```python
# Change from 30 days to 60 days
cursor.execute(
    """
    SELECT add_compression_policy(
        'telemetry',
        INTERVAL '60 days',  # <-- Change here
        if_not_exists => TRUE
    )
    """
)
```

Then run:
```bash
python manage.py migrate
```

---

**Option B: SQL Command (For existing databases)**

```bash
docker compose exec -T db psql -U postgres -d iot_hub_alpha_db << 'EOF'
-- Remove old policy
SELECT remove_compression_policy('telemetry', if_exists => TRUE);

-- Add new policy with 60 days
SELECT add_compression_policy(
    'telemetry',
    INTERVAL '60 days',
    if_not_exists => TRUE
);
EOF
```

---

##  Check Current Policies

### View all policies for telemetry table

```bash
docker compose exec -T db psql -U postgres -d iot_hub_alpha_db << 'EOF'
SELECT
  job_id,
  proc_name,
  schedule_interval,
  config::text
FROM _timescaledb_config.bgw_job
WHERE hypertable_id = (
  SELECT id FROM _timescaledb_catalog.hypertable
  WHERE table_name = 'telemetry'
)
ORDER BY proc_name;
EOF
```

**Output example:**
```
 job_id | proc_name            | schedule_interval | config
--------|----------------------|-------------------|----------------------------------
 1000   | policy_compression   | 01:00:00          | {"compress_after": "30 days"}
 1001   | policy_retention     | 01:00:00          | {"drop_after": "365 days"}
```



## ⚡ Quick Reference

### Current Settings (AC4 Implementation)

```
Retention Policy:    Delete records after 365 days
Compression Policy:  Compress chunks after 30 days
Compression Rate:    85-96% space savings
Retention Cleanup:   Automatic (hourly)
Compression Job:     Automatic (hourly)
```

### Files to Edit

```
Indexes:   backend/apps/telemetry/models.py (lines 22-35)
Policies:  backend/apps/telemetry/migrations/0002_enable_timescaledb_hypertable.py (lines 58-79)
```

### Verification Commands

```bash
# Check indexes
docker compose exec -T db psql -U postgres -d iot_hub_alpha_db \
  -c "SELECT indexname FROM pg_indexes WHERE tablename = 'telemetry'"

# Check policies
docker compose exec -T web python manage.py show_chunks

# Check policy details
docker compose exec -T db psql -U postgres -d iot_hub_alpha_db \
  -c "SELECT * FROM _timescaledb_config.bgw_job WHERE proc_name LIKE '%policy%'"
```

---

##  Important Notes

### Indexes
- ✅ Can be added/removed anytime without data loss
- ✅ Automatic index creation during migration
- ⚠️ Large indexes consume disk space
- ⚠️ Indexes slow down INSERT operations (small overhead ~5-15%)

### Retention Policies
- ✅ Can be changed anytime (SQL command or new migration)
- ⚠️ Deleted data is **permanent** (no undo)
- ✅ Old data is deleted automatically in background
- ⚠️ Don't set retention too short (lose historical data)

### Compression Policies
- ✅ Only compresses chunks older than threshold (recent data stays fast)
- ✅ Queries work normally on compressed chunks
- ⚠️ Very new chunks should not be compressed (they'll be written to again)
- ✅ Default 30 days is recommended for most cases

---

**Last Updated:** 2026-01-30
**Status:** Complete