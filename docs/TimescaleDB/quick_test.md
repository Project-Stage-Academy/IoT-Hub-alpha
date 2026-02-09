## 🔧 Common Tasks

### View what's running in Docker
```bash
docker compose ps
# Shows: web (Django), db (PostgreSQL + TimescaleDB)
```

### Check database connection
```bash
docker compose exec -T db psql -U postgres -d iot_hub_alpha_db -c "SELECT version();"
# Shows: PostgreSQL + TimescaleDB version
```

### View all chunks
```bash
docker compose exec -T web python manage.py show_chunks
# Shows all 14 chunks, sizes, compression status
```

### Compress old chunks manually
```bash
docker compose exec -T web python manage.py compress_chunks
# Compresses chunks older than 30 days (can be changed)
```

### Check policies
```bash
docker compose exec -T db psql -U postgres -d iot_hub_alpha_db << 'EOF'
SELECT * FROM _timescaledb_config.bgw_job WHERE proc_name LIKE '%policy%';
EOF
```