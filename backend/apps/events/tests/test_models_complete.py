"""Complete coverage tests for Event model validators and methods."""

import pytest
from django.core.exceptions import ValidationError

from apps.devices.models import DeviceType, Device
from apps.events.models import (
    Event,
    validate_execution_results,
    validate_telemetry_snapshot,
)
from apps.rules.models import Rule


@pytest.mark.django_db
class TestValidateExecutionResults:
    """Test validate_execution_results validator comprehensively."""

    def test_execution_results_non_list(self):
        """Reject execution_results that are not a list."""
        with pytest.raises(ValidationError, match="must be a list"):
            validate_execution_results({"type": "notification"})

    def test_execution_results_empty_list(self):
        """Accept empty execution_results list."""
        # Should not raise
        validate_execution_results([])

    def test_execution_results_item_not_dict(self):
        """Reject execution_results items that are not dicts."""
        with pytest.raises(ValidationError, match="must be a dictionary"):
            validate_execution_results(["string_item"])

    def test_execution_results_missing_type_field(self):
        """Reject execution results items missing 'type' field."""
        with pytest.raises(ValidationError, match="must have a 'type' field"):
            validate_execution_results([{"status": "completed"}])

    def test_execution_results_missing_status_field(self):
        """Reject execution results items missing 'status' field."""
        with pytest.raises(ValidationError, match="must have a 'status' field"):
            validate_execution_results([{"type": "notification"}])

    def test_execution_results_notification_without_template_id(self):
        """Reject notification results without template_id."""
        with pytest.raises(
            ValidationError, match="Notification result must include template_id"
        ):
            validate_execution_results(
                [{"type": "notification", "status": "completed"}]
            )

    def test_execution_results_notification_with_template_id(self):
        """Accept notification results with template_id."""
        # Should not raise
        validate_execution_results(
            [
                {
                    "type": "notification",
                    "status": "completed",
                    "template_id": 5,
                    "sent_count": 3,
                }
            ]
        )

    def test_execution_results_stop_machine_without_machine_id(self):
        """Reject stop_machine results without machine_id."""
        with pytest.raises(
            ValidationError, match="stop_machine result must include machine_id"
        ):
            validate_execution_results([{"type": "stop_machine", "status": "failed"}])

    def test_execution_results_stop_machine_with_machine_id(self):
        """Accept stop_machine results with machine_id."""
        # Should not raise
        validate_execution_results(
            [
                {
                    "type": "stop_machine",
                    "status": "failed",
                    "machine_id": "M-123",
                    "error": "API timeout",
                }
            ]
        )

    def test_execution_results_multiple_items_mixed(self):
        """Accept multiple execution results with mixed types."""
        # Should not raise
        validate_execution_results(
            [
                {
                    "type": "notification",
                    "status": "completed",
                    "template_id": 5,
                },
                {
                    "type": "stop_machine",
                    "status": "success",
                    "machine_id": "M-456",
                },
            ]
        )


@pytest.mark.django_db
class TestValidateTelemetrySnapshot:
    """Test validate_telemetry_snapshot validator comprehensively."""

    def test_telemetry_snapshot_none(self):
        """Accept None telemetry_snapshot."""
        # Should not raise
        validate_telemetry_snapshot(None)

    def test_telemetry_snapshot_valid_dict_with_payload(self):
        """Accept telemetry snapshot with payload field."""
        # Should not raise
        validate_telemetry_snapshot(
            {
                "device_id": "uuid-123",
                "timestamp": "2026-02-24T12:00:00Z",
                "payload": {"temperature": 25.5, "humidity": 60},
            }
        )

    def test_telemetry_snapshot_non_dict(self):
        """Reject telemetry_snapshot that is not a dict."""
        with pytest.raises(ValidationError, match="must be a JSON object"):
            validate_telemetry_snapshot("not a dict")

    def test_telemetry_snapshot_list(self):
        """Reject telemetry_snapshot that is a list."""
        with pytest.raises(ValidationError, match="must be a JSON object"):
            validate_telemetry_snapshot([1, 2, 3])

    def test_telemetry_snapshot_dict_without_payload(self):
        """Reject telemetry_snapshot dict missing payload field."""
        with pytest.raises(ValidationError, match="should contain 'payload' field"):
            validate_telemetry_snapshot({"device_id": "uuid-123"})

    def test_telemetry_snapshot_empty_dict_accepted(self):
        """Accept empty telemetry_snapshot dict.

        Falsy dicts bypass payload check.
        """
        # Should not raise - empty dict is falsy so the payload check
        # doesn't apply
        validate_telemetry_snapshot({})


@pytest.mark.django_db
class TestEventModel:
    """Test Event model creation and methods."""

    def setup_method(self):
        """Setup test fixtures."""
        self.device_type = DeviceType.objects.create(
            name="Temperature Sensor", metric_unit="°C"
        )
        self.device = Device.objects.create(
            name="Test Device",
            serial_number="TEST-001",
            device_type=self.device_type,
        )
        self.rule = Rule.objects.create(
            device=self.device,
            name="High Temperature Rule",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

    def test_event_str_method(self):
        """Test Event __str__ representation."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Temperature exceeded 25°C",
            status=Event.EventStatus.NEW,
            execution_results=[],
        )

        expected_str = f"Event {event.id} - Rule {self.rule.id} - warning"
        assert str(event) == expected_str

    def test_event_critical_severity(self):
        """Test Event with CRITICAL severity."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.CRITICAL,
            message="System critical alert",
            status=Event.EventStatus.NEW,
            execution_results=[],
        )

        assert event.severity == Event.EventSeverity.CRITICAL
        assert str(event) == (f"Event {event.id} - Rule {self.rule.id} - critical")

    def test_event_info_severity(self):
        """Test Event with INFO severity."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.INFO,
            message="System info message",
            status=Event.EventStatus.NEW,
            execution_results=[],
        )

        assert event.severity == Event.EventSeverity.INFO

    def test_event_acknowledged_property_true(self):
        """Test acknowledged property returns True for non-NEW status."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test event",
            status=Event.EventStatus.ACKNOWLEDGED,
            execution_results=[],
        )

        assert event.acknowledged is True

    def test_event_acknowledged_property_false(self):
        """Test acknowledged property returns False for NEW status."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test event",
            status=Event.EventStatus.NEW,
            execution_results=[],
        )

        assert event.acknowledged is False

    def test_event_resolved_acknowledged(self):
        """Test acknowledged property for RESOLVED status."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.INFO,
            message="Test event",
            status=Event.EventStatus.RESOLVED,
            execution_results=[],
        )

        assert event.acknowledged is True

    def test_event_with_execution_results_structure(self):
        """Test Event with full execution_results structure."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test with execution",
            status=Event.EventStatus.NEW,
            execution_results=[
                {
                    "type": "notification",
                    "status": "completed",
                    "template_id": 5,
                    "sent_count": 3,
                    "completed_at": "2025-01-21T10:00:08Z",
                },
                {
                    "type": "stop_machine",
                    "status": "failed",
                    "machine_id": "M-123",
                    "error": "API timeout",
                },
            ],
        )

        assert len(event.execution_results) == 2
        assert event.execution_results[0]["type"] == "notification"
        assert event.execution_results[1]["type"] == "stop_machine"

    def test_event_with_telemetry_snapshot_full_structure(self):
        """Test Event with full telemetry_snapshot structure."""
        snapshot = {
            "device_id": "uuid-123",
            "timestamp": "2026-02-24T12:00:00Z",
            "payload": {
                "temperature": 27.5,
                "humidity": 65,
                "values": [26.5, 27.0, 27.5],
                "start": "2026-02-24T11:59:00Z",
                "end": "2026-02-24T12:00:00Z",
            },
        }

        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Temperature triggered event",
            status=Event.EventStatus.NEW,
            execution_results=[],
            telemetry_snapshot=snapshot,
        )

        assert event.telemetry_snapshot == snapshot
        assert event.telemetry_snapshot["payload"]["temperature"] == 27.5

    def test_event_cascade_delete_on_rule(self):
        """Test Event is deleted when Rule is deleted."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test cascade",
            status=Event.EventStatus.NEW,
            execution_results=[],
        )

        event_id = event.id
        assert Event.objects.filter(id=event_id).exists()

        self.rule.delete()

        assert not Event.objects.filter(id=event_id).exists()

    def test_event_ordering_by_timestamp_descending(self):
        """Test Event queryset is ordered by timestamp descending."""
        event1 = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="First event",
            status=Event.EventStatus.NEW,
            execution_results=[],
        )

        event2 = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Second event",
            status=Event.EventStatus.NEW,
            execution_results=[],
        )

        events = list(Event.objects.all())
        assert events[0].id == event2.id
        assert events[1].id == event1.id
