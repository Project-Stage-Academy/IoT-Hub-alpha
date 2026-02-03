import pytest
from django.utils import timezone
from unittest.mock import patch
from apps.rules.tasks import process_telemetry
from apps.rules.models import Rule, TelemetryCursor
from apps.telemetry.models import Telemetry
from apps.devices.models import Device, DeviceType


@pytest.fixture
def device(db):
    dt = DeviceType.objects.create(name="type-1", metric_unit="C")
    return Device.objects.create(name="D1", serial_number="dev-1", device_type=dt)


@pytest.fixture
def rule(device, db):
    return Rule.objects.create(
        device=device,
        is_enabled=True,
        condition={"type": "leaf", "operator": "gt", "threshold": 100.0},
        action_config=[{"type": "notification", "template_id": 1}],
    )


@pytest.mark.django_db
def test_persisted_cursor_should_move_forward(device, rule):
    """
    Test telemetry cursor lock
    """
    t1 = Telemetry.objects.create(
        device=device, timestamp=timezone.now(), payload={"value": 50.0}
    )
    t2 = Telemetry.objects.create(
        device=device, timestamp=timezone.now(), payload={"value": 120.0}
    )

    with patch("apps.rules.tasks.trigger_engine") as mock_trigger:
        process_telemetry(cursor_start=0, batch_size=100, record_cursor=True)

        cur = TelemetryCursor.objects.latest("id")
        assert cur.last_id == max(t1.id, t2.id)


@pytest.mark.django_db
def test_first_run_processes_batch_and_triggers(device, rule):
    """
    Test aggregation trigger correctness
    """
    Telemetry.objects.create(
        device=device, timestamp=timezone.now(), payload={"value": 50.0}
    )
    Telemetry.objects.create(
        device=device, timestamp=timezone.now(), payload={"value": 120.0}
    )

    with patch("apps.rules.tasks.trigger_engine") as mock_trigger:
        process_telemetry(cursor_start=0, batch_size=100, record_cursor=False)

        assert mock_trigger.call_count == 1
        (aggregation,), _ = mock_trigger.call_args
        print(aggregation)
        assert rule.id in aggregation
        assert aggregation[rule.id].trigger is True
        assert 120.0 in aggregation[rule.id].values


@pytest.mark.django_db
def test_second_run_does_not_reprocess_old_telemetry_when_cursor_advances(device, rule):
    """
    Test second run dosent write cursor with recor_cursor = False
    """
    t0 = Telemetry.objects.create(
        device=device, timestamp=timezone.now(), payload={"value": 120.0}
    )
    t1 = Telemetry.objects.create(
        device=device, timestamp=timezone.now(), payload={"value": 130.0}
    )

    with patch("apps.rules.tasks.trigger_engine") as mock_trigger:

        process_telemetry(cursor_start=0, batch_size=100, record_cursor=False)
        assert mock_trigger.call_count == 1
        mock_trigger.reset_mock()

        t2 = Telemetry.objects.create(
            device=device, timestamp=timezone.now(), payload={"value": 90.0}
        )
        t3 = Telemetry.objects.create(
            device=device, timestamp=timezone.now(), payload={"value": 150.0}
        )

        process_telemetry(cursor_start=t1.id, batch_size=100, record_cursor=False)

        assert mock_trigger.call_count == 1
        (aggregation,), _ = mock_trigger.call_args

        assert aggregation[rule.id].trigger is True
        assert 150.0 in aggregation[rule.id].values
        assert 130.0 not in aggregation[rule.id].values
