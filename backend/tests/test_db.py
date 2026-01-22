from django.test import TestCase
from django.db import connection
from django.utils import timezone

from apps.devices.models import DeviceType, Device
from apps.telemetry.models import Telemetry
from apps.rules.models import Rule
from apps.events.models import Event
from apps.notifications.models import NotificationTemplate, NotificationDelivery


class DBSmokeTest(TestCase):
    """
    Minimal DB integration/smoke test:
    - Confirms DB is reachable (SELECT 1)
    - Confirms migrations + ORM work end-to-end
    - Exercises basic JSONField queries
    - Does NOT require TimescaleDB extension
    """

    def test_db_connection(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_core_models_workflow(self):
        # DeviceType + Device
        device_type = DeviceType.objects.create(
            name="Smoke Temperature Sensor",
            metric_name="temperature",
            metric_unit="°C",
            metric_min=-10.0,
            metric_max=120.0,
        )

        device = Device.objects.create(
            device_type=device_type,
            name="Smoke Device 1",
            serial_number="SMOKE-SN-0001",
            status="active",
            last_seen=timezone.now(),
        )

        self.assertEqual(DeviceType.objects.count(), 1)
        self.assertEqual(Device.objects.count(), 1)

        # Telemetry
        payload = {
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 22.5,
            "unit": device_type.metric_unit,
        }
        telemetry = Telemetry.objects.create(device=device, payload=payload)

        self.assertIsNotNone(telemetry.id)
        self.assertEqual(telemetry.device_id, device.id)
        self.assertIn("value", telemetry.payload)

        # JSONField query
        self.assertEqual(Telemetry.objects.filter(payload__has_key="value").count(), 1)

        # Rule
        rule = Rule.objects.create(
            device=device,
            name="Smoke High Temperature Rule",
            operator="gt",
            threshold=30.0,
            action_config=[
                {"type": "notification", "template_id": 1},
            ],
            cooldown_minutes=15,
            is_enabled=True,
        )

        self.assertEqual(Rule.objects.filter(device=device, is_enabled=True).count(), 1)

        # Event
        event = Event.objects.create(
            rule=rule,
            telemetry_id=telemetry.id,
            timestamp=timezone.now(),
            severity="warning",
            message="Smoke test event",
            execution_results=[{"type": "notification", "status": "completed"}],
            metadata={"telemetry_snapshot": telemetry.payload},
            status="new",
        )

        self.assertIsNotNone(event.id)
        self.assertEqual(event.rule_id, rule.id)
        self.assertEqual(event.telemetry_id, telemetry.id)
        self.assertEqual(Event.objects.filter(rule__device=device).count(), 1)

        # Notification
        template = NotificationTemplate.objects.create(
            name="Smoke Template",
            message_template="Alert: {message}",
            recipients=[{"type": "email", "address": "smoke@example.com"}],
            priority=1,
            retry_count=3,
            retry_delay_minutes=5,
            is_active=True,
        )

        delivery = NotificationDelivery.objects.create(
            event=event,
            template=template,
            recipient_type="email",
            recipient_address="smoke@example.com",
            recipient_name="Smoke User",
            rendered_message="Alert: Smoke test event",
            status="pending",
            priority=1,
            attempt_count=0,
        )

        self.assertEqual(NotificationTemplate.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 1)
        self.assertEqual(delivery.event_id, event.id)

        # Metadata JSON query
        self.assertEqual(Event.objects.filter(metadata__has_key="telemetry_snapshot").count(), 1)
