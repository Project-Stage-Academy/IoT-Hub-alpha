#!/usr/bin/env sh
set -e

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose is required."
  exit 1
fi

NO_OVERRIDE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --no-override)
      NO_OVERRIDE=1
      ;;
    -h|--help)
      echo "Usage: scripts/reset-db.sh [--no-override]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
  shift
done

COMPOSE_ARGS="-f docker-compose.yml"
if [ "$NO_OVERRIDE" -eq 0 ] && [ -f docker-compose.override.yml ]; then
  COMPOSE_ARGS="$COMPOSE_ARGS -f docker-compose.override.yml"
fi

docker compose $COMPOSE_ARGS up -d db

DB_NAME="$(docker compose $COMPOSE_ARGS exec -T db printenv POSTGRES_DB 2>/dev/null || true)"
DB_USER="$(docker compose $COMPOSE_ARGS exec -T db printenv POSTGRES_USER 2>/dev/null || true)"
DB_NAME="${DB_NAME:-iot_hub_alpha_db}"
DB_USER="${DB_USER:-postgres}"

i=1
max_attempts=30
until docker compose $COMPOSE_ARGS exec -T db pg_isready -U "$DB_USER" >/dev/null 2>&1; do
  if [ "$i" -ge "$max_attempts" ]; then
    echo "Database did not become ready in time."
    exit 1
  fi
  echo "Waiting for database to be ready..."
  i=$((i + 1))
  sleep 2
done

docker compose $COMPOSE_ARGS exec -T db psql -U "$DB_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS \"$DB_NAME\";"
docker compose $COMPOSE_ARGS exec -T db psql -U "$DB_USER" -d postgres \
  -c "CREATE DATABASE \"$DB_NAME\";"

docker compose $COMPOSE_ARGS run --rm migrate

echo "Database reset complete."
