"""Complete coverage tests for EventSerializer."""

import pytest

from apps.devices.models import DeviceType, Device
from apps.events.models import Event
from apps.events.serializer import EventSerializer, ApiValidationError
from apps.rules.models import Rule


@pytest.mark.django_db
class TestApiValidationError:
    """Test ApiValidationError exception."""

    def test_api_validation_error_default_status(self):
        """Test ApiValidationError with default status code."""
        errors = {"field": "Invalid value"}
        exc = ApiValidationError(errors)

        assert exc.errors == errors
        assert exc.status_code == 400
        assert str(exc) == "Validation error"

    def test_api_validation_error_custom_status(self):
        """Test ApiValidationError with custom status code."""
        errors = {"field": "Not found"}
        exc = ApiValidationError(errors, status_code=404)

        assert exc.errors == errors
        assert exc.status_code == 404

    def test_api_validation_error_multiple_fields(self):
        """Test ApiValidationError with multiple field errors."""
        errors = {"field1": "Error 1", "field2": "Error 2"}
        exc = ApiValidationError(errors, status_code=422)

        assert exc.errors == errors
        assert len(exc.errors) == 2


@pytest.mark.django_db
class TestEventSerializerToDict:
    """Test EventSerializer.to_dict() method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
        self.device = Device.objects.create(
            name="Test Device",
            serial_number="TEST-001",
            device_type=self.device_type,
        )
        self.rule = Rule.objects.create(
            device=self.device,
            name="Test Rule",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )

    def test_to_dict_requires_instance(self):
        """Test to_dict() raises error without instance."""
        serializer = EventSerializer(data={})

        with pytest.raises(ValueError, match="instance.*required"):
            serializer.to_dict()

    def test_to_dict_basic_event(self):
        """Test to_dict() with basic event."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test alert",
            status=Event.EventStatus.NEW,
            execution_results=[],
            telemetry_snapshot=None,
        )

        serializer = EventSerializer(instance=event)
        result = serializer.to_dict()

        assert result["id"] == event.id
        assert result["severity"] == "warning"
        assert result["message"] == "Test alert"
        assert result["status"] == "new"
        assert result["rule_id"] == str(self.rule.id)
        assert result["device_id"] == str(self.device.id)
        assert result["acknowledged"] is False
        assert result["payload"] is None

    def test_to_dict_with_telemetry_snapshot(self):
        """Test to_dict() with telemetry snapshot."""
        snapshot = {
            "timestamp": "2026-02-24T10:30:00Z",
            "payload": {"temperature": 26.5},
        }

        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test alert",
            status=Event.EventStatus.NEW,
            execution_results=[],
            telemetry_snapshot=snapshot,
        )

        serializer = EventSerializer(instance=event)
        result = serializer.to_dict()

        assert result["fired_at"] == "2026-02-24T10:30:00Z"
        assert result["payload"] == {"temperature": 26.5}

    def test_to_dict_with_invalid_telemetry_snapshot_type(self):
        """Test to_dict() handles non-dict telemetry_snapshot.

        Should gracefully handle invalid types.
        """
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test alert",
            status=Event.EventStatus.NEW,
            execution_results=[],
            telemetry_snapshot=None,
        )
        # Manually set invalid value (bypassing validator for testing)
        event.telemetry_snapshot = "invalid"
        event.save(update_fields=["telemetry_snapshot"])

        serializer = EventSerializer(instance=event)
        result = serializer.to_dict()

        # Should default to created_at when snapshot is invalid
        assert result["fired_at"] == result["created_at"]
        assert result["payload"] is None

    def test_to_dict_with_missing_timestamp_in_snapshot(self):
        """Test to_dict() when snapshot lacks timestamp field."""
        snapshot = {
            "payload": {"temperature": 26.5},
            # no timestamp field
        }

        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test alert",
            status=Event.EventStatus.NEW,
            execution_results=[],
            telemetry_snapshot=snapshot,
        )

        serializer = EventSerializer(instance=event)
        result = serializer.to_dict()

        # Should fallback to created_at
        assert result["fired_at"] == result["created_at"]

    def test_to_dict_caching(self):
        """Test to_dict() caches result."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test alert",
            status=Event.EventStatus.NEW,
            execution_results=[],
            telemetry_snapshot=None,
        )

        serializer = EventSerializer(instance=event)

        result1 = serializer.to_dict()
        result2 = serializer.to_dict()

        # Should be same object (cached)
        assert result1 is result2

    def test_to_dict_acknowledged_status(self):
        """Test to_dict() with acknowledged event."""
        event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test alert",
            status=Event.EventStatus.ACKNOWLEDGED,
            execution_results=[],
            telemetry_snapshot=None,
        )

        serializer = EventSerializer(instance=event)
        result = serializer.to_dict()

        assert result["acknowledged"] is True


@pytest.mark.django_db
class TestEventSerializerValidate:
    """Test EventSerializer.validate() method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
        self.device = Device.objects.create(
            name="Test Device",
            serial_number="TEST-001",
            device_type=self.device_type,
        )
        self.rule = Rule.objects.create(
            device=self.device,
            name="Test Rule",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )
        self.event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test alert",
            status=Event.EventStatus.NEW,
            execution_results=[],
            telemetry_snapshot=None,
        )

    def test_validate_requires_data(self):
        """Test validate() raises error without data."""
        serializer = EventSerializer(instance=self.event)

        with pytest.raises(ValueError, match="data.*required"):
            serializer.validate()

    def test_validate_missing_required_field(self):
        """Test validate() detects missing required field."""
        serializer = EventSerializer(instance=self.event, data={})

        with pytest.raises(ApiValidationError) as exc_info:
            serializer.validate()

        assert "status" in exc_info.value.errors
        assert exc_info.value.status_code == 400

    def test_validate_valid_status_new(self):
        """Test validate() accepts valid NEW status."""
        serializer = EventSerializer(instance=self.event, data={"status": "new"})

        cleaned = serializer.validate()
        assert cleaned["status"] == "new"

    def test_validate_valid_status_acknowledged(self):
        """Test validate() accepts valid ACKNOWLEDGED status."""
        serializer = EventSerializer(
            instance=self.event, data={"status": "acknowledged"}
        )

        cleaned = serializer.validate()
        assert cleaned["status"] == "acknowledged"

    def test_validate_valid_status_resolved(self):
        """Test validate() accepts valid RESOLVED status."""
        serializer = EventSerializer(instance=self.event, data={"status": "resolved"})

        cleaned = serializer.validate()
        assert cleaned["status"] == "resolved"

    def test_validate_invalid_status(self):
        """Test validate() rejects invalid status value."""
        serializer = EventSerializer(
            instance=self.event, data={"status": "invalid_status"}
        )

        with pytest.raises(ApiValidationError) as exc_info:
            serializer.validate()

        assert "status" in exc_info.value.errors
        assert "Invalid status" in exc_info.value.errors["status"]

    def test_validate_partial_update_no_required_fields(self):
        """Test validate() with partial=True.

        Doesn't require fields.
        """
        serializer = EventSerializer(instance=self.event, data={}, partial=True)

        cleaned = serializer.validate()
        assert cleaned == {}

    def test_validate_partial_update_with_status(self):
        """Test validate() with partial=True accepts status."""
        serializer = EventSerializer(
            instance=self.event, data={"status": "acknowledged"}, partial=True
        )

        cleaned = serializer.validate()
        assert cleaned["status"] == "acknowledged"

    def test_validate_returns_cleaned_dict(self):
        """Test validate() returns only valid write fields."""
        serializer = EventSerializer(
            instance=self.event,
            data={"status": "acknowledged", "extra_field": "ignored"},
        )

        cleaned = serializer.validate()
        assert "status" in cleaned
        assert "extra_field" not in cleaned


@pytest.mark.django_db
class TestEventSerializerSave:
    """Test EventSerializer.save() method."""

    def setup_method(self):
        """Setup test fixtures."""
        self.device_type = DeviceType.objects.create(name="Sensor", metric_unit="°C")
        self.device = Device.objects.create(
            name="Test Device",
            serial_number="TEST-001",
            device_type=self.device_type,
        )
        self.rule = Rule.objects.create(
            device=self.device,
            name="Test Rule",
            is_enabled=True,
            condition={"type": "leaf", "operator": "gt", "threshold": 25.0},
            action_config=[],
        )
        self.event = Event.objects.create(
            rule=self.rule,
            severity=Event.EventSeverity.WARNING,
            message="Test alert",
            status=Event.EventStatus.NEW,
            execution_results=[],
            telemetry_snapshot=None,
        )

    def test_save_requires_instance(self):
        """Test save() raises error without instance."""
        serializer = EventSerializer(data={"status": "acknowledged"})

        with pytest.raises(ValueError, match="instance.*required"):
            serializer.save()

    def test_save_updates_event_status(self):
        """Test save() updates event status."""
        serializer = EventSerializer(
            instance=self.event, data={"status": "acknowledged"}
        )

        updated_event = serializer.save()

        assert updated_event.status == "acknowledged"

        # Verify database was updated
        self.event.refresh_from_db()
        assert self.event.status == "acknowledged"

    def test_save_to_new_status(self):
        """Test save() updates to NEW status."""
        self.event.status = Event.EventStatus.ACKNOWLEDGED
        self.event.save()

        serializer = EventSerializer(instance=self.event, data={"status": "new"})

        updated_event = serializer.save()
        assert updated_event.status == "new"

    def test_save_to_resolved_status(self):
        """Test save() updates to RESOLVED status."""
        serializer = EventSerializer(instance=self.event, data={"status": "resolved"})

        updated_event = serializer.save()
        assert updated_event.status == "resolved"

    def test_save_returns_instance(self):
        """Test save() returns the updated instance."""
        serializer = EventSerializer(
            instance=self.event, data={"status": "acknowledged"}
        )

        result = serializer.save()

        assert isinstance(result, Event)
        assert result.id == self.event.id

    def test_save_validates_before_saving(self):
        """Test save() calls validate first."""
        serializer = EventSerializer(
            instance=self.event, data={"status": "invalid_status"}
        )

        with pytest.raises(ApiValidationError):
            serializer.save()

        # Event should not be modified
        self.event.refresh_from_db()
        assert self.event.status == Event.EventStatus.NEW

    def test_save_partial_update(self):
        """Test save() with partial=True."""
        serializer = EventSerializer(
            instance=self.event, data={"status": "resolved"}, partial=True
        )

        updated_event = serializer.save()
        assert updated_event.status == "resolved"

    def test_save_transaction_atomic(self):
        """Test save() uses atomic transaction."""
        serializer = EventSerializer(
            instance=self.event, data={"status": "acknowledged"}
        )

        # Should execute without transaction errors
        result = serializer.save()
        assert result.status == "acknowledged"
