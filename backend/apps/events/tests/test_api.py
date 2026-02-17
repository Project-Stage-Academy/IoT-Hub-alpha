import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client
from django.utils import timezone

from apps.devices.models import DeviceType, Device
from apps.events.models import Event
from apps.rules.models import Rule


def _make_user_with_perms(*codenames: str):
    user = get_user_model().objects.create_user(
        username="tester",
        password="test-pass-123",
        email="tester@example.com",
    )
    if codenames:
        perms = Permission.objects.filter(codename__in=codenames)
        user.user_permissions.add(*perms)
    return user


@pytest.mark.django_db
def test_events_list_filters_and_acknowledged():
    dt = DeviceType.objects.create(name="temp", metric_unit="C")
    dev1 = Device.objects.create(name="Device-1", serial_number="D-001", device_type=dt)
    dev2 = Device.objects.create(name="Device-2", serial_number="D-002", device_type=dt)
    rule1 = Rule.objects.create(
        device=dev1,
        name="Rule-1",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )
    rule2 = Rule.objects.create(
        device=dev2,
        name="Rule-2",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )

    Event.objects.create(
        rule=rule1,
        timestamp=timezone.now(),
        severity=Event.EventSeverity.WARNING,
        message="event-1",
        execution_results=[],
        telemetry_snapshot={
            "device_id": str(dev1.id),
            "timestamp": "2026-01-15T10:30:00+00:00",
            "payload": {"values": [11.0]},
        },
        status=Event.EventStatus.NEW,
    )
    Event.objects.create(
        rule=rule2,
        timestamp=timezone.now(),
        severity=Event.EventSeverity.INFO,
        message="event-2",
        execution_results=[],
        telemetry_snapshot={
            "device_id": str(dev2.id),
            "timestamp": timezone.now().isoformat(),
            "payload": {"values": [12.0]},
        },
        status=Event.EventStatus.ACKNOWLEDGED,
    )

    user = _make_user_with_perms("view_event")
    client = Client()
    client.force_login(user)

    resp = client.get(f"/api/v1/events/?device_id={dev1.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["message"] == "event-1"
    assert body["data"][0]["fired_at"] == "2026-01-15T10:30:00+00:00"
    assert body["data"][0]["created_at"] != body["data"][0]["fired_at"]
    assert body["data"][0]["acknowledged"] is False

    resp = client.get("/api/v1/events/?acknowledged=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["message"] == "event-2"
    assert body["data"][0]["acknowledged"] is True


@pytest.mark.django_db
def test_events_ack_updates_status():
    dt = DeviceType.objects.create(name="temp", metric_unit="C")
    dev = Device.objects.create(name="Device-1", serial_number="D-001", device_type=dt)
    rule = Rule.objects.create(
        device=dev,
        name="Rule-1",
        condition={"type": "leaf", "operator": "gt", "threshold": 10.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )
    event = Event.objects.create(
        rule=rule,
        timestamp=timezone.now(),
        severity=Event.EventSeverity.WARNING,
        message="event-1",
        execution_results=[],
        telemetry_snapshot={
            "device_id": str(dev.id),
            "timestamp": timezone.now().isoformat(),
            "payload": {"values": [11.0]},
        },
        status=Event.EventStatus.NEW,
    )

    user = _make_user_with_perms("change_event", "view_event")
    client = Client()
    client.force_login(user)

    resp = client.post(f"/api/v1/events/{event.id}/ack/")
    assert resp.status_code == 200
    event.refresh_from_db()
    assert event.status == Event.EventStatus.ACKNOWLEDGED
    assert resp.json()["data"]["status"] == Event.EventStatus.ACKNOWLEDGED
