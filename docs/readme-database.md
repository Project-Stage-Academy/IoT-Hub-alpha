# IoT Hub Alpha - Database Operations Guide

## Table of Contents

1. [Quick Start](#quick-start)
2. [Database Setup](#database-setup)
3. [Running Migrations](#running-migrations)
4. [Database Access](#database-access)
5. [Seeding Data](#seeding-data)
6. [Backup and Restore](#backup-and-restore)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### First Time Setup

```bash
# 1. Copy environment file and configure
cp .env.example .env

# 2. Start the database
docker compose up -d db

# 3. Wait for database to be ready (check health)
docker compose ps

# 4. Run migrations
docker compose run --rm migrate

# 5. Set up TimescaleDB hypertables
docker compose run --rm web python manage.py setup_timescaledb

# 6. Create superuser
docker compose run --rm web python manage.py createsuperuser

# 7. Load seed data
docker compose run --rm web python scripts/seed_data.py

# 8. Start all services
docker compose up
```

Access the admin panel at: http://localhost:8000/admin

---

## Database Setup

### PostgreSQL with TimescaleDB

The project uses **TimescaleDB** (PostgreSQL extension) for efficient time-series data storage.

**Container Configuration:**
- **Image**: `timescale/timescaledb:latest-pg15`
- **Port**: 5432 (mapped to host)
- **Volume**: `postgres_data` (persistent storage)

### Environment Variables

Configure in `.env` file:

```bash
# Database credentials
DB_NAME=iot_hub_alpha_db
DB_USER=postgres
DB_PASSWORD=your_secure_password_here
DB_HOST=db
DB_PORT=5432

# Connection pool settings (optional)
DB_CONN_MAX_AGE=60
DB_CONN_HEALTH_CHECKS=True

# Telemetry retention
TELEMETRY_RETENTION_DAYS=90
```

### Database Extensions

Automatically enabled via `scripts/init-db.sh`:
- ✅ `timescaledb` - Time-series optimization
- ✅ `uuid-ossp` - UUID generation

---

## Running Migrations

### Create Migrations

After modifying models:

```bash
# Create migrations for all apps
docker compose run --rm web python manage.py makemigrations

# Create migrations for specific app
docker compose run --rm web python manage.py makemigrations devices

# Check migration SQL (dry-run)
docker compose run --rm web python manage.py sqlmigrate devices 0001
```

### Apply Migrations

```bash
# Apply all pending migrations
docker compose run --rm migrate

# Apply specific app migrations
docker compose run --rm migrate devices

# Migrate to specific migration
docker compose run --rm migrate devices 0002

# Show migration status
docker compose run --rm web python manage.py showmigrations
```

### Rollback Migrations

```bash
# Rollback to previous migration
docker compose run --rm migrate devices 0001

# Rollback all migrations for an app (careful!)
docker compose run --rm migrate devices zero
```

### Initial Migration Workflow

```bash
# 1. Create initial migrations for all apps
docker compose run --rm web python manage.py makemigrations

# 2. Apply migrations to create tables
docker compose run --rm migrate

# 3. Set up TimescaleDB hypertables (MUST run after migrate)
docker compose run --rm web python manage.py setup_timescaledb
```

**⚠️ Important:** Always run `setup_timescaledb` AFTER the initial migration to convert the `telemetry` table to a hypertable.

---

## Database Access

### Using psql in Container

#### Method 1: Docker Compose Exec

```bash
# Connect to database
docker compose exec db psql -U postgres -d iot_hub_alpha_db

# One-liner query
docker compose exec db psql -U postgres -d iot_hub_alpha_db -c "SELECT COUNT(*) FROM telemetry;"
```

#### Method 2: Docker Compose Run

```bash
# Interactive psql session
docker compose run --rm db psql -h db -U postgres -d iot_hub_alpha_db
```

### Common psql Commands

```sql
-- List all databases
\l

-- Connect to database
\c iot_hub_alpha_db

-- List all tables
\dt

-- Describe table structure
\d devices
\d+ telemetry

-- List all indexes
\di

-- Show table sizes
\dt+

-- List all extensions
\dx

-- Check TimescaleDB hypertables
SELECT * FROM timescaledb_information.hypertables;

-- Check TimescaleDB chunks
SELECT * FROM timescaledb_information.chunks 
WHERE hypertable_name = 'telemetry';

-- Exit psql
\q
```

### Using Django Shell

```bash
# Start Django shell
docker compose run --rm web python manage.py shell

# Or use iPython if available
docker compose run --rm web python manage.py shell_plus
```

**Example Django shell queries:**

```python
from apps.devices.models import Device, DeviceType
from apps.telemetry.models import Telemetry
from apps.rules.models import Rule
from apps.events.models import Event

# Get device count
Device.objects.count()

# Get recent telemetry
Telemetry.objects.order_by('-timestamp')[:10]

# Get active devices
Device.objects.filter(status='active')

# Execute raw SQL
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) FROM telemetry")
    print(cursor.fetchone())
```

### Database Users and Roles

#### Create Read-Only User

```bash
docker compose exec db psql -U postgres -d iot_hub_alpha_db
```

```sql
-- Create read-only user for reporting tools
CREATE USER iot_readonly WITH PASSWORD 'secure_password_here';

-- Grant connect permission
GRANT CONNECT ON DATABASE iot_hub_alpha_db TO iot_readonly;

-- Grant usage on public schema
GRANT USAGE ON SCHEMA public TO iot_readonly;

-- Grant SELECT on all existing tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO iot_readonly;

-- Grant SELECT on future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
  GRANT SELECT ON TABLES TO iot_readonly;

-- Test connection
\c iot_hub_alpha_db iot_readonly
SELECT COUNT(*) FROM devices;
```

#### Create Application User (Production)

```sql
-- Create dedicated application user
CREATE USER iot_app WITH PASSWORD 'strong_password_here';

-- Grant connect and schema usage
GRANT CONNECT ON DATABASE iot_hub_alpha_db TO iot_app;
GRANT USAGE ON SCHEMA public TO iot_app;

-- Grant full permissions on all tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO iot_app;

-- Grant sequence usage
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO iot_app;

-- Grant future permissions
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO iot_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
  GRANT USAGE, SELECT ON SEQUENCES TO iot_app;
```

---

## Seeding Data

### Method 1: Django Fixtures (JSON)

```bash
# Load initial data fixture
docker compose run --rm web python manage.py loaddata fixtures/initial_data.json

# Create your own fixture from existing data
docker compose run --rm web python manage.py dumpdata devices --indent 2 > backend/fixtures/devices.json
```

### Method 2: Python Seed Script (Recommended)

```bash
# Run comprehensive seed script
docker compose run --rm web python scripts/seed_data.py
```

**What it creates:**
- 3 device types (vibration_sensor, temperature_sensor, power_meter)
- 4 devices (active and inactive)
- 3 rules (alert thresholds)
- 60 telemetry records (20 per device)

### Method 3: Django Admin Interface

1. Start the server: `docker compose up`
2. Navigate to http://localhost:8000/admin
3. Login with superuser credentials
4. Manually create records through the UI

### Verify Seeded Data

```bash
# Check counts via Django shell
docker compose run --rm web python manage.py shell
```

```python
from apps.devices.models import DeviceType, Device
from apps.telemetry.models import Telemetry
from apps.rules.models import Rule

print(f"Device Types: {DeviceType.objects.count()}")
print(f"Devices: {Device.objects.count()}")
print(f"Rules: {Rule.objects.count()}")
print(f"Telemetry: {Telemetry.objects.count()}")
```

---

## Backup and Restore

### Backup Strategies

#### 1. Full Database Backup (pg_dump)

**Create Backup:**

```bash
# Backup to file in backups/ directory
docker compose exec db pg_dump -U postgres iot_hub_alpha_db > backups/iot_hub_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
docker compose exec db pg_dump -U postgres iot_hub_alpha_db | gzip > backups/iot_hub_$(date +%Y%m%d_%H%M%S).sql.gz

# Custom format (faster restore, parallel)
docker compose exec db pg_dump -U postgres -Fc iot_hub_alpha_db > backups/iot_hub_$(date +%Y%m%d_%H%M%S).dump
```

**Restore Backup:**

```bash
# Restore from SQL file
docker compose exec -T db psql -U postgres iot_hub_alpha_db < backups/iot_hub_20250119_120000.sql

# Restore from compressed file
gunzip -c backups/iot_hub_20250119_120000.sql.gz | docker compose exec -T db psql -U postgres iot_hub_alpha_db

# Restore from custom format
docker compose exec db pg_restore -U postgres -d iot_hub_alpha_db /path/to/backup.dump
```

#### 2. Schema-Only Backup

```bash
# Backup only schema (no data)
docker compose exec db pg_dump -U postgres -s iot_hub_alpha_db > backups/schema_only.sql

# Restore schema
docker compose exec -T db psql -U postgres iot_hub_alpha_db < backups/schema_only.sql
```

#### 3. Data-Only Backup

```bash
# Backup only data (no schema)
docker compose exec db pg_dump -U postgres -a iot_hub_alpha_db > backups/data_only.sql

# Restore data
docker compose exec -T db psql -U postgres iot_hub_alpha_db < backups/data_only.sql
```

#### 4. Specific Table Backup

```bash
# Backup single table
docker compose exec db pg_dump -U postgres -t telemetry iot_hub_alpha_db > backups/telemetry_backup.sql

# Backup multiple tables
docker compose exec db pg_dump -U postgres -t devices -t device_types iot_hub_alpha_db > backups/devices_backup.sql
```

### Automated Backup Script

Create `scripts/backup_db.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="iot_hub_alpha_db"
RETENTION_DAYS=30

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# Create backup
echo "Creating backup: ${BACKUP_DIR}/iot_hub_${TIMESTAMP}.sql.gz"
docker compose exec -T db pg_dump -U postgres "$DB_NAME" | gzip > "${BACKUP_DIR}/iot_hub_${TIMESTAMP}.sql.gz"

# Verify backup
if [ -f "${BACKUP_DIR}/iot_hub_${TIMESTAMP}.sql.gz" ]; then
    echo "✅ Backup created successfully: $(du -h ${BACKUP_DIR}/iot_hub_${TIMESTAMP}.sql.gz | cut -f1)"
else
    echo "❌ Backup failed!"
    exit 1
fi

# Delete old backups (older than RETENTION_DAYS)
echo "Cleaning up old backups (keeping last ${RETENTION_DAYS} days)..."
find "$BACKUP_DIR" -name "iot_hub_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "✅ Backup completed successfully!"
```

Make it executable:

```bash
chmod +x scripts/backup_db.sh
```

Run it:

```bash
./scripts/backup_db.sh
```

### Automated Cron Job (Linux/macOS)

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * cd /path/to/IoT-Hub-alpha && ./scripts/backup_db.sh >> /var/log/iot_backup.log 2>&1

# Add weekly backup every Sunday at 3 AM
0 3 * * 0 cd /path/to/IoT-Hub-alpha && ./scripts/backup_db.sh >> /var/log/iot_backup.log 2>&1
```

### Docker Volume Backup

```bash
# Backup the entire PostgreSQL data volume
docker run --rm \
  -v iot-hub-alpha_postgres_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/postgres_volume_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

# Restore volume
docker run --rm \
  -v iot-hub-alpha_postgres_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/postgres_volume_20250119_120000.tar.gz -C /data
```

### Staging Environment Restore

To restore production backup to staging:

```bash
# 1. Stop staging services
docker compose -f docker-compose.staging.yml down

# 2. Drop and recreate database
docker compose -f docker-compose.staging.yml up -d db
docker compose -f docker-compose.staging.yml exec db psql -U postgres -c "DROP DATABASE IF EXISTS iot_hub_alpha_db;"
docker compose -f docker-compose.staging.yml exec db psql -U postgres -c "CREATE DATABASE iot_hub_alpha_db;"

# 3. Restore from production backup
gunzip -c backups/production_backup.sql.gz | \
  docker compose -f docker-compose.staging.yml exec -T db psql -U postgres iot_hub_alpha_db

# 4. Re-run TimescaleDB setup
docker compose -f docker-compose.staging.yml run --rm backend python manage.py setup_timescaledb

# 5. Start services
docker compose -f docker-compose.staging.yml up -d
```

---

## Troubleshooting

### Database Connection Issues

**Problem**: Can't connect to database

```bash
# Check if database is running
docker compose ps db

# Check database logs
docker compose logs db

# Check health status
docker compose exec db pg_isready -U postgres

# Test connection
docker compose exec db psql -U postgres -c "SELECT 1;"
```

**Problem**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
1. Verify `DB_HOST=db` in `.env`
2. Ensure database container is running: `docker compose up -d db`
3. Wait for health check to pass: `docker compose ps`

### Migration Issues

**Problem**: `django.db.migrations.exceptions.InconsistentMigrationHistory`

**Solution**:

```bash
# Show current migration status
docker compose run --rm web python manage.py showmigrations

# Fake migrations if tables already exist
docker compose run --rm migrate --fake

# Or reset migrations (development only!)
docker compose down -v  # Remove volumes
docker compose up -d db
docker compose run --rm migrate
```

**Problem**: `ProgrammingError: relation "telemetry" does not exist`

**Solution**: Run migrations before running the app

```bash
docker compose run --rm migrate
```

### TimescaleDB Issues

**Problem**: `ERROR: extension "timescaledb" is not available`

**Solution**: Verify TimescaleDB image is used in `docker-compose.yml`:

```yaml
db:
  image: timescale/timescaledb:latest-pg15  # NOT postgres:15-alpine
```

**Problem**: `ERROR: table "telemetry" is already a hypertable`

This is normal on subsequent runs. The command is idempotent.

### Performance Issues

**Check slow queries:**

```sql
-- Enable pg_stat_statements (run once)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Find slow queries
SELECT 
  query,
  calls,
  mean_exec_time,
  max_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 100  -- queries slower than 100ms
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**Check missing indexes:**

```sql
SELECT 
  schemaname, 
  tablename, 
  indexname, 
  idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
ORDER BY tablename;
```

### Disk Space Issues

**Check database size:**

```sql
SELECT 
  pg_size_pretty(pg_database_size('iot_hub_alpha_db')) as database_size;

SELECT 
  schemaname,
  tablename,
  pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Solution**: Adjust telemetry retention or enable compression

```bash
# Update retention in .env
TELEMETRY_RETENTION_DAYS=30  # Reduce from 90 days

# Re-run setup
docker compose run --rm web python manage.py setup_timescaledb
```

## Quick Reference

### Common Commands

```bash
# Database access
docker compose exec db psql -U postgres -d iot_hub_alpha_db

# Run migrations
docker compose run --rm migrate

# Create superuser
docker compose run --rm web python manage.py createsuperuser

# Load seed data
docker compose run --rm web python scripts/seed_data.py

# Setup TimescaleDB
docker compose run --rm web python manage.py setup_timescaledb

# Backup database
docker compose exec db pg_dump -U postgres iot_hub_alpha_db | gzip > backups/backup_$(date +%Y%m%d).sql.gz

# Restore database
gunzip -c backups/backup_20250119.sql.gz | docker compose exec -T db psql -U postgres iot_hub_alpha_db

# Check database size
docker compose exec db psql -U postgres -d iot_hub_alpha_db -c "SELECT pg_size_pretty(pg_database_size('iot_hub_alpha_db'));"
```

### Useful SQL Queries

```sql
-- Count records in all tables
SELECT 
  schemaname,
  tablename,
  n_tup_ins - n_tup_del as row_count
FROM pg_stat_user_tables
ORDER BY tablename;

-- Recent telemetry by device
SELECT 
  d.name,
  COUNT(*) as telemetry_count,
  MAX(t.timestamp) as last_telemetry
FROM devices d
LEFT JOIN telemetry t ON d.id = t.device_id
GROUP BY d.id, d.name
ORDER BY last_telemetry DESC;

-- Active rules
SELECT 
  r.name,
  d.name as device_name,
  r.metric_name,
  r.operator,
  r.threshold
FROM rules r
JOIN devices d ON r.device_id = d.id
WHERE r.is_enabled = true;
```

---

## Related Documentation

- [Schema Documentation](./schema.md) - Detailed table structures and relationships
- [API Documentation](./api.yaml) - REST API endpoints
- [README](../README.md) - Project overview and setup
