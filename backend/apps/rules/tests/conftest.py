import pytest
from django.utils import timezone
from apps.devices.models import DeviceType, Device
from apps.rules.models import Rule, TelemetryCursor
from apps.notifications.models import NotificationTemplate
from apps.events.models import Event
from apps.telemetry.models import Telemetry


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


# Additional fixtures for process_telemetry task testing
@pytest.fixture
def device_with_rule(db):
    """Create device with a rule for process_telemetry testing."""
    dt = DeviceType.objects.create(name="sensor-type", metric_unit="°C")
    dev = Device.objects.create(
        name="Test Sensor",
        serial_number="SENSOR-001",
        device_type=dt,
        status="active",
    )
    rule = Rule.objects.create(
        device=dev,
        is_enabled=True,
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[{"type": "log", "message": "High temperature"}],
    )
    return {"device": dev, "rule": rule}


@pytest.fixture
def multiple_devices_with_rules(db):
    """Create multiple devices with rules for multi-device testing."""
    dt = DeviceType.objects.create(name="multi-sensor", metric_unit="°C")

    # Device 1
    dev1 = Device.objects.create(
        name="Sensor 1",
        serial_number="SN-001",
        device_type=dt,
        status="active",
    )
    rule1 = Rule.objects.create(
        device=dev1,
        is_enabled=True,
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[{"type": "log", "message": "High temp"}],
    )

    # Device 2
    dev2 = Device.objects.create(
        name="Sensor 2",
        serial_number="SN-002",
        device_type=dt,
        status="active",
    )
    rule2 = Rule.objects.create(
        device=dev2,
        is_enabled=True,
        condition={"type": "leaf", "operator": "lt", "threshold": 20.0},
        action_config=[{"type": "log", "message": "Low temp"}],
    )

    return {
        "devices": [dev1, dev2],
        "rules": [rule1, rule2],
    }


@pytest.fixture
def telemetry_for_processing(db, device_with_rule):
    """Create telemetry records for process_telemetry testing."""
    device = device_with_rule["device"]
    records = []

    # Create 3 telemetry records with different values
    for i, value in enumerate([45.0, 55.0, 65.0]):  # Middle one should trigger rule
        telemetry = Telemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload={
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": value,
            },
        )
        records.append(telemetry)

    return records


@pytest.fixture
def cursor_initial(db):
    """Create initial cursor for incremental processing."""
    return TelemetryCursor.objects.create(name="Main Cursor", last_id=0)


@pytest.fixture
def disabled_rule(db, device_with_rule):
    """Create disabled rule that should not be evaluated."""
    device = device_with_rule["device"]
    return Rule.objects.create(
        device=device,
        is_enabled=False,  # Disabled
        condition={"type": "leaf", "operator": "gt", "threshold": 30.0},
        action_config=[{"type": "log", "message": "Should not trigger"}],
    )
