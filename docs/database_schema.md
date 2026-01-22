# IoT Hub Alpha - Database Schema Documentation

## Overview

This document describes the PostgreSQL database schema for the IoT Hub Alpha MVP, including table structures, relationships, indexes, and optimization strategies using TimescaleDB for time-series telemetry data.

## Technology Stack

- **Database**: PostgreSQL 15
- **Extensions**: TimescaleDB (time-series optimization), UUID-OSSP (UUID generation)
- **ORM**: Django 6.0.1
- **Connection Pooling**: psycopg2-binary with connection pooling enabled

## Database Schema Diagram

```
┌─────────────────────┐          ┌─────────────────────┐
│   device_types      │          │ notification_       │
├─────────────────────┤          │ templates           │
│ PK id (UUID)        │          ├─────────────────────┤
│    name             │          │ PK id (BIGSERIAL)   │
│    description      │          │    name             │
│    metric_name      │          │    message_template │
│    metric_unit      │          │    recipients (JSONB)│
│    metric_min       │          │    priority         │
│    metric_max       │          │    retry_count      │
│    created_at       │          │    retry_delay_mins │
└─────────────────────┘          │    is_active        │
         │                       │    created_at       │
         │                       │    updated_at       │
         │                       └─────────────────────┘
         │ FK device_type_id                │
         │                                  │
┌────────▼──────────┐                       │
│     devices       │                       │
├───────────────────┤                       │
│ PK id (UUID)      │                       │
│    name           │                       │
│    serial_number  │                       │
│    location       │                       │
│    status         │◄────────┐             │
│    last_seen      │         │             │
│    created_at     │         │             │
│    updated_at     │         │             │
└───────────────────┘         │             │
         │                    │ FK device_id│
         │                    │             │
         │                    │             │
    ┌────▼──────────┐  ┌──────▼────────┐    │
    │  telemetry    │  │     rules     │    │
    ├───────────────┤  ├───────────────┤    │
    │PK id (BIGINT) │  │PK id (UUID)   │    │
    │FK device_id   │  │FK device_id   │    │
    │  timestamp    │  │  name         │    │
    │  payload      │  │  description  │    │
    └───────────────┘  │  operator     │    │
         ▲             │  threshold    │    │
         │             │  action_config│◄───┘
         │             │  cooldown_mins│    
         │             │  last_trigger │    
         │             │  is_enabled   │    
         │             │  created_at   │    
         │             │  updated_at   │    
         │             └───────────────┘    
         │                     │            
         │                     │ FK rule_id 
         │                     ▼            
         │            ┌─────────────────┐   
         │            │   events        │   
         │            ├─────────────────┤   
         │            │PK id (BIGINT)   │   
         │            │FK rule_id       │   
         └────────────┤   telemetry_id │   
                      │   timestamp    │◄────┐
                      │   severity     │     │
                      │   message      │     │
                      │   execution_   │     │
                      │     results    │     │
                      │   metadata     │     │
                      │   status       │     │
                      └─────────────────┘     │
                              │               │
                              │               │
                              │               │
                              │ FK event_id   │ FK event_id
                              │               │
                              ▼               │
                     ┌────────────────────┐   │
                     │ notification_      │   │
                     │ deliveries         │   │
                     ├────────────────────┤   │
                     │PK id (BIGSERIAL)   │◄──┘
                     │FK event_id         │
                     │FK template_id      │
                     │   recipient_type   │
                     │   recipient_address│
                     │   recipient_name   │
                     │   rendered_message │
                     │   status           │
                     │   priority         │
                     │   attempt_count    │
                     │   last_attempt_at  │
                     │   error_message    │
                     │   sent_at          │
                     │   created_at       │
                     └────────────────────┘
```

## Table Definitions

### 1. device_types

Defines types of IoT devices with their expected metric information.

| Column           | Type          | Constraints               | Description                                    |
|------------------|---------------|---------------------------|------------------------------------------------|
| id               | UUID          | PRIMARY KEY               | Unique identifier                              |
| name             | VARCHAR(100)  | UNIQUE, NOT NULL          | Device type name (e.g., vibration_sensor)      |
| description      | TEXT          | NULL                      | Detailed description                           |
| metric_name      | VARCHAR(20)   | NOT NULL (Enum)           | Primary metric (vibration, temperature, pressure) |
| metric_unit      | VARCHAR(50)   | NOT NULL                  | Unit of measurement (mm_s, celsius, etc.)      |
| metric_min       | DECIMAL(15,4) | NULL                      | Minimum expected value                         |
| metric_max       | DECIMAL(15,4) | NULL                      | Maximum expected value                         |
| created_at       | TIMESTAMP     | NOT NULL, DEFAULT NOW()   | Creation timestamp                             |

**Indexes:**
- `idx_device_type_name` on `name` 
- `idx_device_type_metric` on `metric_name`

### 2. devices

Individual IoT device instances deployed in the field.

| Column           | Type          | Constraints                 | Description                                    |
|------------------|---------------|----------------------------|------------------------------------------------|
| id               | UUID          | PRIMARY KEY                | Unique identifier                              |
| device_type_id   | UUID          | FK → device_types.id, NOT NULL | Reference to device type                   |
| name             | VARCHAR(255)  | NOT NULL                   | Human-readable device name                     |
| serial_number    | VARCHAR(100)  | UNIQUE, NOT NULL           | Manufacturer serial number                     |
| location         | TEXT          | NULL                       | Physical location (e.g., Workshop A)           |
| status           | VARCHAR(20)   | NOT NULL, DEFAULT 'active' | active, inactive, error                        |
| last_seen        | TIMESTAMP     | NULL                       | Last telemetry received timestamp              |
| created_at       | TIMESTAMP     | NOT NULL, DEFAULT NOW()    | Creation timestamp                             |
| updated_at       | TIMESTAMP     | NOT NULL, DEFAULT NOW()    | Last update timestamp                          |

**Indexes:**
- `idx_device_serial` on `serial_number`
- `idx_device_type` on `device_type_id`
- `idx_device_status_last_seen` on `(status, last_seen)`

### 3. telemetry (TimescaleDB Hypertable)

Time-series telemetry data from devices. This table is converted to a TimescaleDB hypertable for optimized time-series queries.

| Column           | Type          | Constraints               | Description                                    |
|------------------|---------------|---------------------------|------------------------------------------------|
| id               | BIGSERIAL     | PRIMARY KEY               | Auto-incrementing identifier                   |
| device_id        | UUID          | FK → devices.id, NOT NULL | Device that generated the telemetry            |
| timestamp        | TIMESTAMP     | NOT NULL, DEFAULT NOW()   | When telemetry was recorded                    |
| payload          | JSONB         | NOT NULL                  | Telemetry data with version and measurements   |

**Indexes:**
- `idx_telemetry_device_time` on `(device_id, timestamp)` - Primary query pattern
- `idx_telemetry_payload_gin` (GIN) on `payload` - JSONB flexible queries

**TimescaleDB Configuration:**
- Partitioned by: `timestamp`
- Chunk interval: 7 days (default)
- Compression: Enabled for data older than 30 days
- Retention policy: 1 year (configurable)

**Example payload:**
```json
{
  "version": "0.0.1",
  "serial_number": "VIB-SN-001",
  "metrics": {
    "vibration": 5.2,
    "temperature": 45.3,
    "operating_hours": 1250
  }
}
```

### 4. rules

Rule definitions for triggering events based on telemetry thresholds.

| Column            | Type          | Constraints               | Description                                    |
|-------------------|---------------|---------------------------|------------------------------------------------|
| id                | UUID          | PRIMARY KEY               | Unique identifier                              |
| device_id         | UUID          | FK → devices.id, NOT NULL | Device to monitor                              |
| name              | VARCHAR(255)  | NOT NULL                  | Rule name                                      |
| description       | TEXT          | NULL                      | Detailed description                           |
| operator          | VARCHAR(10)   | NOT NULL                  | gt, lt, gte, lte, eq, neq                      |
| threshold         | DECIMAL(15,4) | NOT NULL                  | Threshold value                                |
| action_config     | JSONB         | NOT NULL                  | Actions to take when rule triggered            |
| cooldown_minutes  | INTEGER       | DEFAULT 15                | Minimum minutes between triggers               |
| last_triggered_at | TIMESTAMP     | NULL                      | When rule was last triggered                   |
| is_enabled        | BOOLEAN       | DEFAULT TRUE              | Rule active status                             |
| created_at        | TIMESTAMP     | NOT NULL, DEFAULT NOW()   | Creation timestamp                             |
| updated_at        | TIMESTAMP     | NOT NULL, DEFAULT NOW()   | Last update timestamp                          |

**Indexes:**
- `idx_rule_device_enabled` on `(device_id, is_enabled)`
- `idx_rule_is_enabled` on `is_enabled`
- `idx_rule_last_triggered` on `last_triggered_at`
- `idx_rule_action_config_gin` (GIN) on `action_config`

**Example action_config:**
```json
[
  {
    "type": "notification",
    "template_id": 5,
    "recipients": ["admin@company.com"]
  },
  {
    "type": "stop_machine",
    "machine_id": "M-123"
  }
]
```

### 5. events

Events triggered by rule evaluations.

| Column           | Type          | Constraints               | Description                                    |
|------------------|---------------|---------------------------|------------------------------------------------|
| id               | BIGSERIAL     | PRIMARY KEY               | Auto-incrementing identifier                   |
| rule_id          | UUID          | FK → rules.id, NOT NULL   | Rule that triggered the event                  |
| telemetry_id     | BIGINT        | NULL                      | Reference to triggering telemetry (no FK)      |
| timestamp        | TIMESTAMP     | NOT NULL, DEFAULT NOW()   | Event occurrence time                          |
| severity         | VARCHAR(20)   | NOT NULL                  | critical, warning, info                        |
| message          | TEXT          | NOT NULL                  | Human-readable event description               |
| execution_results| JSONB         | NOT NULL                  | Results of actions taken                       |
| metadata         | JSONB         | NULL                      | Additional context, telemetry snapshot         |
| status           | VARCHAR(20)   | NOT NULL, DEFAULT 'new'   | new, acknowledged, resolved                    |

**Indexes:**
- `idx_event_rule` on `rule_id`
- `idx_event_telemetry` on `telemetry_id`
- `idx_event_status_time` on `(status, timestamp)`
- `idx_event_time_severity_status` on `(timestamp, severity, status)`
- `idx_event_execution_results_gin` (GIN) on `execution_results`

**Example execution_results:**
```json
[
  {
    "type": "notification",
    "template_id": 5,
    "status": "completed",
    "sent_count": 3,
    "completed_at": "2025-01-21T10:00:08Z"
  },
  {
    "type": "stop_machine",
    "machine_id": "M-123",
    "status": "failed",
    "error": "API timeout"
  }
]
```

### 6. notification_templates

Templates for notifications to be sent when events occur.

| Column              | Type          | Constraints               | Description                                    |
|---------------------|---------------|---------------------------|------------------------------------------------|
| id                  | BIGSERIAL     | PRIMARY KEY               | Auto-incrementing identifier                   |
| name                | VARCHAR(100)  | UNIQUE, NOT NULL          | Template name                                  |
| message_template    | TEXT          | NOT NULL                  | Message with placeholders                      |
| recipients          | JSONB         | NOT NULL                  | Default recipients configuration               |
| priority            | INTEGER       | DEFAULT 1                 | Delivery priority (lower = higher priority)    |
| retry_count         | INTEGER       | DEFAULT 3                 | Max retry attempts                             |
| retry_delay_minutes | INTEGER       | DEFAULT 5                 | Minutes between retry attempts                 |
| is_active           | BOOLEAN       | DEFAULT TRUE              | Template active status                         |
| created_at          | TIMESTAMP     | NOT NULL, DEFAULT NOW()   | Creation timestamp                             |
| updated_at          | TIMESTAMP     | NOT NULL, DEFAULT NOW()   | Last update timestamp                          |

**Indexes:**
- `idx_notification_template_name` on `name`
- `idx_notification_template_active` on `is_active` 
- `idx_notification_template_priority` on `priority`
- `idx_notification_template_recipients_gin` (GIN) on `recipients`

**Example recipients:**
```json
[
  {"type": "email", "address": "admin@company.com"},
  {"type": "sms", "phone": "+380501234567"},
  {"type": "webhook", "url": "https://hooks.slack.com/services/XXX/YYY/ZZZ"}
]
```

### 7. notification_deliveries

Records of notification delivery attempts.

| Column             | Type          | Constraints               | Description                                    |
|--------------------|---------------|---------------------------|------------------------------------------------|
| id                 | BIGSERIAL     | PRIMARY KEY               | Auto-incrementing identifier                   |
| event_id           | BIGINT        | FK → events.id, NOT NULL (CASCADE) | Associated event                      |
| template_id        | BIGINT        | FK → notification_templates.id, NOT NULL | Template used                  |
| recipient_type     | VARCHAR(20)   | NOT NULL                  | email, sms, webhook                            |
| recipient_address  | TEXT          | NOT NULL                  | Email address, phone, webhook URL              |
| recipient_name     | VARCHAR(255)  | NULL                      | Human-readable recipient name                  |
| rendered_message   | TEXT          | NOT NULL                  | Final message with placeholders filled         |
| status             | VARCHAR(20)   | NOT NULL, DEFAULT 'pending' | pending, sent, failed                       |
| priority           | INTEGER       | DEFAULT 1                 | Delivery priority (lower = higher priority)    |
| attempt_count      | INTEGER       | DEFAULT 0                 | Number of delivery attempts                    |
| last_attempt_at    | TIMESTAMP     | NULL                      | Last attempt timestamp                         |
| error_message      | TEXT          | NULL                      | Error details if failed                        |
| sent_at            | TIMESTAMP     | NULL                      | Successful delivery timestamp                  |
| created_at         | TIMESTAMP     | NOT NULL, DEFAULT NOW()   | Creation timestamp                             |

**Indexes:**
- `idx_notification_delivery_event` on `event_id`
- `idx_notification_delivery_queue` on `(status, priority, created_at)` 
- `idx_notification_delivery_retry` on `(status, attempt_count, last_attempt_at)`

## TimescaleDB Integration

### Docker Compose Configuration

Add TimescaleDB to your Docker Compose file:

```yaml
services:
  db:
    image: timescale/timescaledb:latest-pg15
    environment:
      - POSTGRES_DB=${DB_NAME:-iot_hub_alpha_db}
      - POSTGRES_USER=${DB_USER:-postgres}
      - POSTGRES_PASSWORD=${DB_PASSWORD:-postgres}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-db.sh:/docker-entrypoint-initdb.d/init-db.sh
    ports:
      - "5432:5432"
```

### Hypertable Creation

After running migrations, execute the TimescaleDB setup command:

```bash
docker compose run --rm web python manage.py setup_timescaledb
```

This command:
1. Converts the `telemetry` table to a TimescaleDB hypertable
2. Creates a GIN index on the JSONB `payload` column
3. Sets up retention policy
4. Enables compression for older data

### Hypertable Setup in Django

Configure the hypertable setup command:

```python
# apps/telemetry/management/commands/setup_timescaledb.py
def handle(self, *args, **options):
    with connection.cursor() as cursor:
        # Check if TimescaleDB extension is enabled
        cursor.execute("SELECT extname FROM pg_extension WHERE extname='timescaledb';")
        if cursor.fetchone() is None:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
            
        # Create hypertable
        cursor.execute("""
            SELECT create_hypertable(
                'telemetry',
                'timestamp',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """)
        
        # Add compression policy
        cursor.execute("""
            ALTER TABLE telemetry SET (
              timescaledb.compress,
              timescaledb.compress_segmentby = 'device_id'
            );
            
            SELECT add_compression_policy(
                'telemetry', 
                INTERVAL '30 days'
            );
        """)
        
        # Add retention policy for 1 year
        cursor.execute("""
            SELECT add_retention_policy(
                'telemetry',
                INTERVAL '1 year'
            );
        """)
```

## Query Optimization Examples

### Example: Recent Telemetry with GIN Filtering

This query demonstrates efficient use of both the device-time index and the payload GIN index:

```sql
EXPLAIN ANALYZE
SELECT t.timestamp, t.payload, d.name as device_name
FROM telemetry t
JOIN devices d ON t.device_id = d.id
WHERE t.device_id = 'd4e5f6a7-b8c9-4012-d345-456789012def'
  AND t.timestamp > NOW() - INTERVAL '24 hours'
  AND t.payload @> '{"metrics": {"vibration": {}}}'
  AND (t.payload->'metrics'->'vibration')::numeric > 15
ORDER BY t.timestamp DESC
LIMIT 100;
```

**Expected Execution Plan:**
```
Limit  (cost=25.26..35.49 rows=8 width=352)
  ->  Sort  (cost=25.26..25.28 rows=8 width=352)
        Sort Key: t."timestamp" DESC
        ->  Nested Loop  (cost=5.14..24.83 rows=8 width=352)
              ->  Bitmap Heap Scan on telemetry t  (cost=4.71..17.96 rows=8 width=336)
                    Recheck Cond: (((device_id = 'd4e5f6a7-...'::uuid) AND 
                                  ("timestamp" > (now() - '24:00:00'::interval))) AND 
                                  (payload @> '{"metrics": {"vibration": {}}}'::jsonb))
                    Filter: ((payload -> 'metrics'::text) -> 'vibration'::text)::numeric > '15'::numeric
                    ->  BitmapAnd  (cost=4.71..4.71 rows=8 width=0)
                          ->  Bitmap Index Scan on idx_telemetry_device_time  (cost=0.00..1.73 rows=40 width=0)
                                Index Cond: ((device_id = 'd4e5f6a7-...'::uuid) AND 
                                           ("timestamp" > (now() - '24:00:00'::interval)))
                          ->  Bitmap Index Scan on idx_telemetry_payload_gin  (cost=0.00..2.97 rows=21 width=0)
                                Index Cond: (payload @> '{"metrics": {"vibration": {}}}'::jsonb)
              ->  Index Scan using devices_pkey on devices d  (cost=0.42..0.85 rows=1 width=40)
                    Index Cond: (id = t.device_id)
Planning Time: 1.245 ms
Execution Time: 3.876 ms
```

This query is optimized by:
1. Using the device-time index to filter by device and time
2. Using the JSONB GIN index to efficiently find records with vibration metrics
3. Applying a numeric filter on the vibration value

## Security Considerations

1. **Database credentials**: Store in `.env`, never commit to Git
2. **Connection encryption**: Use SSL in production
3. **Role-based access**: Create read-only users for reporting tools
4. **Telemetry retention**: Configure retention policy based on data volume and regulatory requirements
5. **SQL injection protection**: Use Django ORM's parameterized queries

## Related Documentation

- [Database Operations Guide](./readme-database.md) - Setup, migrations, backup procedures
- [API Documentation](./api.yaml) - REST API endpoints
