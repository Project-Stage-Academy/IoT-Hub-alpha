import pytest
from django.utils import timezone

from apps.devices.models import DeviceType, Device
from apps.events.models import Event
from apps.notifications.models import NotificationTemplate, NotificationDelivery
from apps.rules.models import Rule
from apps.rules.tasks import process_telemetry
from apps.telemetry.models import Telemetry
from apps.notifications import tasks as notif_tasks


@pytest.mark.django_db
def test_process_telemetry_creates_event_and_deliveries(monkeypatch):
    dt = DeviceType.objects.create(name="temp", metric_unit="C")
    dev = Device.objects.create(name="Device-1", serial_number="D-001", device_type=dt)
    template = NotificationTemplate.objects.create(
        id=1,
        name="Ops Alert",
        message_template="ALERT: {severity}",
        recipients=[
            {"type": "email", "address": "ops@factory.com"},
            {"type": "sms", "phone": "+380501234567"},
        ],
        priority=2,
        retry_count=1,
        retry_delay_minutes=1,
        is_active=True,
    )
    rule = Rule.objects.create(
        device=dev,
        name="Rule-1",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": template.id}],
        is_enabled=True,
    )
    Telemetry.objects.create(
        device=dev,
        payload={
            "schema_version": "1.0",
            "serial_number": dev.serial_number,
            "value": 42.0,
        },
    )

    # Avoid Celery broker usage in tests.
    monkeypatch.setattr(
        notif_tasks.process_notification_delivery,
        "delay",
        lambda *_args, **_kwargs: None,
    )

    process_telemetry.run(cursor_start=0, batch_size=100, record_cursor=False)

    event = Event.objects.get(rule=rule)
    assert event.message
    assert event.severity in {
        Event.EventSeverity.INFO,
        Event.EventSeverity.WARNING,
        Event.EventSeverity.CRITICAL,
    }
    assert event.execution_results
    assert event.execution_results[0]["status"] == "queued"

    deliveries = NotificationDelivery.objects.filter(event=event)
    assert deliveries.count() == 2
