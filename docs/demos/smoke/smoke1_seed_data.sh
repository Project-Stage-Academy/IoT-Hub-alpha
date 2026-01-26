#!/usr/bin/env bash
set -euo pipefail

export DJANGO_LOG_LEVEL=WARNING

SERVICE="${SERVICE:-web}"
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

echo "Taking counts before re-seed..."
before="$(docker compose exec -T "$SERVICE" $DJANGO_SHELL "
from apps.devices.models import DeviceType, Device
from apps.rules.models import Rule
from apps.notifications.models import NotificationTemplate
print(DeviceType.objects.count(), Device.objects.count(), NotificationTemplate.objects.count(), Rule.objects.count())
")"

echo "Re-running seed..."
docker compose exec -T "$SERVICE" $SEED_CMD

echo "Taking counts after re-seed..."
after="$(docker compose exec -T "$SERVICE" $DJANGO_SHELL "
from apps.devices.models import DeviceType, Device
from apps.rules.models import Rule
from apps.notifications.models import NotificationTemplate
print(DeviceType.objects.count(), Device.objects.count(), NotificationTemplate.objects.count(), Rule.objects.count())
")"

test "$before" = "$after" || { echo "❌ Not idempotent: before=$before after=$after"; exit 1; }
echo "✅ Idempotency verified: $after"