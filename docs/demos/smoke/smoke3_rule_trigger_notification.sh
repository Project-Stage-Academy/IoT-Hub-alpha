#!/usr/bin/env bash
set -euo pipefail

SERVICE="${SERVICE:-web}"
SIM_SERVICE="${SIM_SERVICE:-simulator}"

DEVICE="${DEVICE:-rule_trigger_power}"
COUNT="${COUNT:-1}"
RATE="${RATE:-0.5}"

echo "Seeding demo data..."
docker compose exec -T "$SERVICE" python manage.py seed_data

echo "Capturing notification count before..."
before=$(
  docker compose exec -T "$SERVICE" python manage.py shell -c "
from apps.notifications.models import NotificationDelivery
print(NotificationDelivery.objects.count())
" | tr -d '\r' | tail -n 1
)

echo "Sending triggering telemetry..."
docker compose run --rm simulator \
  --files demo2.json \
  --mode http \
  --rate "$RATE" \
  --count "$COUNT"

# Add manual rule triggering worker here when its done.

echo "Capturing notification count after..."
after=$(
  docker compose exec -T "$SERVICE" python manage.py shell -c "
from apps.notifications.models import NotificationDelivery
print(NotificationDelivery.objects.count())
" | tr -d '\r' | tail -n 1
)

echo "Before=$before After=$after"
if [ "$after" -le "$before" ]; then
  echo "Expected NotificationDelivery to increase, but it did not."
  exit 1
fi

echo "✅ rule trigger smoke OK"
