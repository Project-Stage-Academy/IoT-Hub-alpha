import pytest

from apps.events.models import Event
from apps.notifications.models import NotificationDelivery, NotificationTemplate
from apps.rules.models import Rule
from tests.utils.rule_processor import process_telemetry_for_device


@pytest.mark.django_db
def test_integration_flow_triggers_event_and_delivery(device, telemetry_factory):
    template = NotificationTemplate.objects.create(
        name="High Temp Alert",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=3,
        retry_delay_minutes=5,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="High Temp",
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=True,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 55.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert len(events) == 1
    assert Event.objects.count() == 1
    assert NotificationDelivery.objects.count() == 1
    delivery = NotificationDelivery.objects.first()
    assert delivery.status == NotificationDelivery.NotificationStatus.PENDING


@pytest.mark.django_db
def test_integration_flow_no_event_when_threshold_not_met(device, telemetry_factory):
    template = NotificationTemplate.objects.create(
        name="Low Temp Alert",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=3,
        retry_delay_minutes=5,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="High Temp",
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=True,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 45.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert events == []
    assert Event.objects.count() == 0
    assert NotificationDelivery.objects.count() == 0


@pytest.mark.django_db
def test_integration_flow_no_event_when_rule_disabled(device, telemetry_factory):
    template = NotificationTemplate.objects.create(
        name="Disabled Rule Alert",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "alerts@example.com"}],
        priority=1,
        retry_count=3,
        retry_delay_minutes=5,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="Disabled Rule",
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=False,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 55.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert events == []
    assert Event.objects.count() == 0
    assert NotificationDelivery.objects.count() == 0


@pytest.mark.django_db
def test_integration_flow_multiple_recipients_create_multiple_deliveries(
    device, telemetry_factory
):
    template = NotificationTemplate.objects.create(
        name="Multi Recipient Alert",
        message_template="Alert {severity}: {message}",
        recipients=[
            {"type": "email", "address": "alerts@example.com"},
            {"type": "sms", "phone": "+15550001111"},
        ],
        priority=1,
        retry_count=3,
        retry_delay_minutes=5,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="High Temp",
        condition={"type": "leaf", "operator": "gt", "threshold": 50.0},
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=True,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 55.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert len(events) == 1
    assert Event.objects.count() == 1
    assert NotificationDelivery.objects.count() == 2
