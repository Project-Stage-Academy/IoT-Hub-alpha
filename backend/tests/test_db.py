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

    def setUp(self):
        """Set up common test data for device tests."""
        # Create device type
        self.device_type = DeviceType.objects.create(
            name="Smoke Temperature Sensor",
            metric_name="temperature",
            metric_unit="°C",
            metric_min=-10.0,
            metric_max=120.0,
        )

        # Create device
        self.device = Device.objects.create(
            device_type=self.device_type,
            name="Smoke Device 1",
            serial_number="SMOKE-SN-0001",
            status="active",
            last_seen=timezone.now(),
        )

        # Create telemetry
        self.payload = {
            "version": "1.0.0",
            "serial_number": self.device.serial_number,
            "value": 22.5,
            "unit": self.device_type.metric_unit,
        }
        self.telemetry = Telemetry.objects.create(
            device=self.device, payload=self.payload
        )

        # Create rule
        self.rule = Rule.objects.create(
            device=self.device,
            name="Smoke High Temperature Rule",
            comparison_operator="gt",
            threshold=30.0,
            action_config=[
                {"type": "notification", "template_id": 1, "cooldown_minutes": 15},
            ],
            is_enabled=True,
        )

        # Create event
        self.event = Event.objects.create(
            rule=self.rule,
            timestamp=timezone.now(),
            severity="warning",
            message="Smoke test event",
            execution_results=[{"type": "notification", "status": "completed"}],
            telemetry_snapshot={
                "device_id": str(self.device.id),
                "timestamp": self.telemetry.timestamp.isoformat(),
                "payload": self.telemetry.payload,
            },
            status="new",
        )

        # Create notification template and delivery
        self.template = NotificationTemplate.objects.create(
            name="Smoke Template",
            message_template="Alert: {message}",
            recipients=[{"type": "email", "address": "smoke@example.com"}],
            priority=1,
            retry_count=3,
            retry_delay_minutes=5,
            is_active=True,
        )

        self.delivery = NotificationDelivery.objects.create(
            event=self.event,
            template=self.template,
            notification_type=NotificationDelivery.NotificationType.EMAIL,
            recipient_address="smoke@example.com",
            recipient_name="Smoke User",
            rendered_message="Alert: Smoke test event",
            status=NotificationDelivery.NotificationStatus.PENDING,
            attempt_count=0,
        )

    def test_device_type_and_device_creation(self):
        """Test creating device types and devices."""
        self.assertEqual(DeviceType.objects.count(), 1)
        self.assertEqual(Device.objects.count(), 1)
        self.assertEqual(self.device.device_type, self.device_type)
        self.assertEqual(self.device.name, "Smoke Device 1")

    def test_telemetry_creation(self):
        """Test telemetry creation and JSON fields."""
        self.assertIsNotNone(self.telemetry.id)
        self.assertEqual(self.telemetry.device_id, self.device.id)
        self.assertIn("value", self.telemetry.payload)
        self.assertEqual(self.telemetry.payload["value"], 22.5)

    def test_telemetry_json_queries(self):
        """Test querying JSON fields in telemetry."""
        self.assertEqual(Telemetry.objects.filter(payload__has_key="value").count(), 1)
        self.assertEqual(Telemetry.objects.filter(payload__value=22.5).count(), 1)

    def test_rule_creation(self):
        """Test rule creation and querying."""
        self.assertEqual(
            Rule.objects.filter(device=self.device, is_enabled=True).count(), 1
        )
        self.assertEqual(self.rule.name, "Smoke High Temperature Rule")
        self.assertEqual(self.rule.comparison_operator, "gt")
        self.assertEqual(float(self.rule.threshold), 30.0)

    def test_event_creation(self):
        """Test event creation and relationships."""
        self.assertIsNotNone(self.event.id)
        self.assertEqual(self.event.rule_id, self.rule.id)
        self.assertIsNotNone(self.event.telemetry_snapshot)
        self.assertEqual(Event.objects.filter(rule__device=self.device).count(), 1)

    def test_event_telemetry_snapshot(self):
        """Test event telemetry snapshot queries."""
        self.assertEqual(
            Event.objects.filter(telemetry_snapshot__has_key="payload").count(), 1
        )
        self.assertEqual(
            self.event.telemetry_snapshot["device_id"], str(self.device.id)
        )
        self.assertIn("payload", self.event.telemetry_snapshot)

    def test_notification_creation(self):
        """Test notification template and delivery creation."""
        self.assertEqual(NotificationTemplate.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 1)
        self.assertEqual(self.delivery.event_id, self.event.id)
        self.assertEqual(self.delivery.template_id, self.template.id)

    def test_notification_template_json(self):
        """Test notification template JSON handling."""
        self.assertEqual(len(self.template.recipients), 1)
        self.assertEqual(self.template.recipients[0]["type"], "email")
        self.assertEqual(self.template.recipients[0]["address"], "smoke@example.com")
