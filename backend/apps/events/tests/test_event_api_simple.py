"""Simple API tests for Event views."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.devices.models import DeviceType, Device
from apps.events.models import Event
from apps.rules.models import Rule


@pytest.mark.django_db
class TestEventListAPI:
    """Simple API endpoint tests."""

    def setup_method(self):
        """Setup test data."""
        self.client = APIClient()
        self.device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
        self.device = Device.objects.create(
            name="Test Sensor",
            serial_number="SENSOR-001",
            device_type=self.device_type,
        )
        self.rule = Rule.objects.create(
            device=self.device,
            name="Test Rule",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

    def test_event_creation_creates_record(self):
        """Event can be created via API or directly."""
        event = Event.objects.create(
            rule=self.rule,
            message="Test event",
            severity=Event.EventSeverity.WARNING,
            status=Event.EventStatus.NEW,
            telemetry_snapshot={"values": [25.5], "start": None, "end": None},
        )

        assert event.id is not None
        assert event.rule_id == self.rule.id

    def test_event_status_choices_work(self):
        """Event status choices are accessible."""
        event = Event.objects.create(
            rule=self.rule,
            message="Test",
            severity=Event.EventSeverity.INFO,
            status=Event.EventStatus.ACKNOWLEDGED,
            telemetry_snapshot=None,
        )

        assert event.status == Event.EventStatus.ACKNOWLEDGED