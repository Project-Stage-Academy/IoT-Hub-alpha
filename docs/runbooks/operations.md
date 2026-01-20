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
