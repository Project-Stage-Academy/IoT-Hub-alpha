import pytest
from django.utils import timezone
from apps.devices.models import DeviceType, Device
from apps.rules.models import Rule
from apps.notifications.models import NotificationTemplate
from apps.events.models import Event


@pytest.fixture
def rule_model(db):
    dt = DeviceType.objects.create(name="type-1", metric_unit="C")
    dev = Device.objects.create(name="Device-01", serial_number="dev-1", device_type=dt)
    return Rule.objects.create(
        device=dev,
        is_enabled=True,
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": 1}],
    )


@pytest.fixture
def notif_template_model(db):
    return NotificationTemplate.objects.create(
        id=1,
        priority=2,
        message_template="{severity} {device_name} {value}{unit}",
        recipients=[{"type": "email", "address": "tests@b.com"}],
    )


@pytest.fixture
def event_model(db, rule_model, notif_template_model):
    return Event.objects.create(
        rule=rule_model,
        timestamp=timezone.now(),
        severity=notif_template_model.priority,
        message="existing",
        execution_results={"status": "new"},
        telemetry_snapshot={"values": [1.0], "start": None, "end": None},
        status=Event.EventStatus.NEW,
    )
