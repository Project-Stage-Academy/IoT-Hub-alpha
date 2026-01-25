#!/usr/bin/env bash
set -euo pipefail

SERVICE="${SERVICE:-web}"
DEVICE="${DEVICE:-device1}"
RATE="${RATE:-0.5}"
COUNT="${COUNT:-3}"

echo "$DEVICE"

echo "Seeding demo data (needed so device exists)..."
docker compose exec -T "$SERVICE" python manage.py seed_data

echo "Sending $COUNT telemetry messages over HTTP via local simulator..."
docker compose run --rm simulator python -m simulator.run \
  --mode http \
  --device "$DEVICE" \
  --rate "$RATE" \
  --count "$COUNT"

echo "✅ ingest HTTP smoke OK"
