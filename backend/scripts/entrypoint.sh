#!/bin/sh
set -e

python - <<'PY'
import os
import time
import psycopg2

host = os.getenv("DB_HOST", "db")
port = os.getenv("DB_PORT", "5432")
name = os.getenv("DB_NAME", "postgres")
user = os.getenv("DB_USER", "postgres")
password = os.getenv("DB_PASSWORD", "postgres")

deadline = time.time() + 60
last_error = None
while time.time() < deadline:
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            dbname=name,
            user=user,
            password=password,
            connect_timeout=3,
        )
        conn.close()
        print("Database is ready.")
        raise SystemExit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(2)

print(f"Database not ready after 60s: {last_error}")
raise SystemExit(1)
PY

exec "$@"
