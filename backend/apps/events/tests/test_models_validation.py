"""Additional tests for Event model validation coverage."""

import pytest
from django.core.exceptions import ValidationError

from apps.devices.models import DeviceType, Device
from apps.events.models import Event, validate_telemetry_snapshot
from apps.rules.models import Rule


@pytest.mark.django_db
class TestTelemetrySnapshotValidation:
    """Test telemetry_snapshot validation edge cases."""

    def test_validate_telemetry_snapshot_with_none(self):
        """validate_telemetry_snapshot accepts None gracefully."""
        # Should not raise any exception
        result = validate_telemetry_snapshot(None)
        assert result is None

    def test_validate_telemetry_snapshot_with_dict(self):
        """validate_telemetry_snapshot accepts valid dict with payload."""
        snapshot = {
            "payload": {
                "values": [25.5, 26.0],
                "start": "2026-02-24T12:00:00Z",
                "end": "2026-02-24T12:01:00Z",
            }
        }
        # Should not raise
        validate_telemetry_snapshot(snapshot)

    def test_validate_telemetry_snapshot_rejects_non_dict(self):
        """validate_telemetry_snapshot rejects non-dict values."""
        with pytest.raises(ValidationError):
            validate_telemetry_snapshot("not a dict")

    def test_event_with_none_telemetry_snapshot(self):
        """Event can be created with None telemetry_snapshot."""
        dt = DeviceType.objects.create(name="Sensor", metric_unit="°C")
        device = Device.objects.create(
            name="Test Sensor",
            serial_number="SENSOR-TEST",
            device_type=dt,
        )
        rule = Rule.objects.create(
            device=device,
            name="Test Rule",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

        # Create event with None telemetry_snapshot - should be valid
        event = Event.objects.create(
            rule=rule,
            message="Test event",
            severity=Event.EventSeverity.WARNING,
            status=Event.EventStatus.NEW,
            telemetry_snapshot=None,
        )

        assert event.id is not None
        assert event.telemetry_snapshot is None
