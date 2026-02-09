import pytest

from apps.events.models import Event
from apps.notifications.models import NotificationDelivery, NotificationTemplate
from apps.rules.models import Rule
from tests.utils.rule_processor import process_telemetry_for_device


@pytest.mark.django_db
@pytest.mark.smoke
def test_smoke_device_telemetry_rule_event_flow(device, telemetry_factory):
    template = NotificationTemplate.objects.create(
        name="Smoke Alert",
        message_template="Alert {severity}: {message}",
        recipients=[{"type": "email", "address": "smoke@example.com"}],
        priority=1,
        retry_count=1,
        retry_delay_minutes=1,
        is_active=True,
    )
    Rule.objects.create(
        device=device,
        name="Smoke Rule",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=True,
    )
    telemetry = telemetry_factory(
        payload={
            "version": "1.0.0",
            "serial_number": device.serial_number,
            "value": 25.0,
            "unit": device.device_type.metric_unit,
        }
    )

    events = process_telemetry_for_device(telemetry)

    assert len(events) == 1
    assert Event.objects.count() == 1
    assert NotificationDelivery.objects.count() == 1
