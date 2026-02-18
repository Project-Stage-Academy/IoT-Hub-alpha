import pytest
from types import SimpleNamespace
from django.utils import timezone

from apps.devices.models import DeviceType, Device
from apps.events.models import Event
from apps.notifications.models import NotificationTemplate, NotificationDelivery
from apps.rules.models import Rule
from apps.notifications import tasks as notif_tasks


class RetryCalled(Exception):
    def __init__(self, countdown):
        self.countdown = countdown


def _push_request(task, retries: int) -> None:
    task.request_stack.push(SimpleNamespace(retries=retries))


def _pop_request(task) -> None:
    task.request_stack.pop()


@pytest.mark.django_db
def test_webhook_retry_updates_execution_results(monkeypatch):
    dt = DeviceType.objects.create(name="temp", metric_unit="C")
    dev = Device.objects.create(name="Device-1", serial_number="D-001", device_type=dt)
    rule = Rule.objects.create(
        device=dev,
        name="Rule-1",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )
    template = NotificationTemplate.objects.create(
        id=1,
        name="Webhook Alert",
        message_template="ALERT: {severity}",
        recipients=[{"type": "webhook", "url": "https://example.com"}],
        priority=2,
        retry_count=2,
        retry_delay_minutes=1,
        is_active=True,
    )
    event = Event.objects.create(
        rule=rule,
        timestamp=timezone.now(),
        severity=Event.EventSeverity.WARNING,
        message="event-1",
        execution_results=[
            {
                "type": "notification",
                "template_id": template.id,
                "status": "queued",
                "recipient_count": 1,
            }
        ],
        telemetry_snapshot={
            "device_id": str(dev.id),
            "timestamp": timezone.now().isoformat(),
            "payload": {"values": [11.0]},
        },
        status=Event.EventStatus.NEW,
    )
    delivery = NotificationDelivery.objects.create(
        event=event,
        template=template,
        notification_type=NotificationDelivery.NotificationType.WEBHOOK,
        recipient_address="https://example.com",
        rendered_message="hello",
    )

    monkeypatch.setattr(notif_tasks, "WEBHOOKS_ENABLED", True)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(notif_tasks, "_post_webhook", _boom)

    def _retry(exc=None, countdown=None):
        raise RetryCalled(countdown)

    task = notif_tasks.process_notification_delivery
    monkeypatch.setattr(task, "retry", _retry)

    _push_request(task, retries=0)
    try:
        with pytest.raises(RetryCalled) as excinfo:
            task.run(delivery.id)
    finally:
        _pop_request(task)

    delivery.refresh_from_db()
    event.refresh_from_db()

    assert excinfo.value.countdown == 60
    assert delivery.status == NotificationDelivery.NotificationStatus.PENDING
    assert delivery.attempt_count == 1
    assert delivery.error_message == "boom"
    assert event.execution_results[0]["status"] == "queued"
    assert event.execution_results[0]["pending_count"] == 1


@pytest.mark.django_db
def test_webhook_max_retries_marks_failed(monkeypatch):
    dt = DeviceType.objects.create(name="temp", metric_unit="C")
    dev = Device.objects.create(name="Device-1", serial_number="D-001", device_type=dt)
    rule = Rule.objects.create(
        device=dev,
        name="Rule-1",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )
    template = NotificationTemplate.objects.create(
        id=1,
        name="Webhook Alert",
        message_template="ALERT: {severity}",
        recipients=[{"type": "webhook", "url": "https://example.com"}],
        priority=2,
        retry_count=2,
        retry_delay_minutes=1,
        is_active=True,
    )
    event = Event.objects.create(
        rule=rule,
        timestamp=timezone.now(),
        severity=Event.EventSeverity.WARNING,
        message="event-1",
        execution_results=[
            {
                "type": "notification",
                "template_id": template.id,
                "status": "queued",
                "recipient_count": 1,
            }
        ],
        telemetry_snapshot={
            "device_id": str(dev.id),
            "timestamp": timezone.now().isoformat(),
            "payload": {"values": [11.0]},
        },
        status=Event.EventStatus.NEW,
    )
    delivery = NotificationDelivery.objects.create(
        event=event,
        template=template,
        notification_type=NotificationDelivery.NotificationType.WEBHOOK,
        recipient_address="https://example.com",
        rendered_message="hello",
    )

    monkeypatch.setattr(notif_tasks, "WEBHOOKS_ENABLED", True)

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(notif_tasks, "_post_webhook", _boom)

    task = notif_tasks.process_notification_delivery

    def _retry(*args, **kwargs):
        raise AssertionError("retry should not be called at max retries")

    monkeypatch.setattr(task, "retry", _retry)
    _push_request(task, retries=2)
    try:
        task.run(delivery.id)
    finally:
        _pop_request(task)

    delivery.refresh_from_db()
    event.refresh_from_db()

    assert delivery.status == NotificationDelivery.NotificationStatus.FAILED
    assert event.execution_results[0]["status"] == "failed"
