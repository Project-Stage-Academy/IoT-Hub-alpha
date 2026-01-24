#!/usr/bin/env bash
set -euo pipefail

export DJANGO_LOG_LEVEL=WARNING

SERVICE="${SERVICE:-web}"              # docker compose service running Django
SEED_CMD="${SEED_CMD:-python manage.py seed_data}"
DJANGO_SHELL="${DJANGO_SHELL:-python manage.py shell -c}"

echo "Seeding demo data..."
docker compose exec -T "$SERVICE" $SEED_CMD

echo "Asserting core objects exist..."
docker compose exec -T "$SERVICE" $DJANGO_SHELL "

from apps.devices.models import DeviceType, Device
from apps.rules.models import Rule
from apps.notifications.models import NotificationTemplate
assert DeviceType.objects.count() > 0, 'No DeviceTypes created'
assert Device.objects.count() > 0, 'No Devices created'
assert NotificationTemplate.objects.count() > 0, 'No NotificationTemplates created'
assert Rule.objects.count() > 0, 'No Rules created'
print('OK counts:',
      'device_types=', DeviceType.objects.count(),
      'devices=', Device.objects.count(),
      'templates=', NotificationTemplate.objects.count(),
      'rules=', Rule.objects.count())
"

echo "Re-running seed to verify idempotency (counts should not explode)..."
docker compose exec -T "$SERVICE" $SEED_CMD

docker compose exec -T "$SERVICE" $DJANGO_SHELL "

from apps.devices.models import DeviceType, Device
from apps.rules.models import Rule
from apps.notifications.models import NotificationTemplate

dt = DeviceType.objects.count()
dv = Device.objects.count()
nt = NotificationTemplate.objects.count()
rl = Rule.objects.count()

assert dt < 1000 and dv < 10000 and nt < 1000 and rl < 10000, 'Counts look suspiciously high after re-seed'
print('OK idempotency-ish counts:', dt, dv, nt, rl)
"

echo "✅ seed/admin smoke OK"