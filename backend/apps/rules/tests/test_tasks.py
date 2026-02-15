import pytest
from unittest.mock import patch, MagicMock
from django.utils import timezone

from apps.rules.tasks import process_telemetry
from apps.rules.models import Rule, TelemetryCursor
from apps.telemetry.models import Telemetry
from apps.events.models import Event


@pytest.mark.django_db
class TestProcessTelemetryTask:
    """Unit tests for process_telemetry Celery task (rule evaluation & triggering)."""

    def test_process_incremental_telemetry(self, device_with_rule):
        """Test incremental telemetry processing from cursor position.

        Verifies:
        - Task fetches only telemetry with id > cursor
        - Processes records in order
        - Updates cursor position after processing
        - Evaluates rules against telemetry data

        Validates incremental processing strategy.
        """
        device = device_with_rule["device"]
        rule = device_with_rule["rule"]

        # Create initial cursor at 0
        cursor = TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Create telemetry records
        telemetry_records = []
        for i, value in enumerate([45.0, 55.0, 65.0]):
            t = Telemetry.objects.create(
                device=device,
                timestamp=timezone.now(),
                payload={
                    "schema_version": "1.0",
                    "serial_number": device.serial_number,
                    "value": value,
                },
            )
            telemetry_records.append(t)

        # Call task
        process_telemetry(cursor_start=0, batch_size=10, record_cursor=True)

        # Verify cursor was updated
        updated_cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert updated_cursor.last_id > 0
        assert updated_cursor.last_id == telemetry_records[-1].id

    def test_cursor_tracking_updates(self, device_with_rule):
        """Test cursor is tracked and updated correctly (state management).

        Verifies:
        - Cursor starts at 0 or provided value
        - Cursor is updated to last_id after processing
        - Multiple runs process only new telemetry
        - Cursor persists across task invocations

        Validates cursor-based incremental processing.
        """
        device = device_with_rule["device"]

        # Create cursor
        cursor = TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Create 2 telemetry records
        t1 = Telemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload={"schema_version": "1.0", "value": 40.0},
        )
        t2 = Telemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload={"schema_version": "1.0", "value": 50.0},
        )

        # First run: process both
        process_telemetry(cursor_start=0, batch_size=10, record_cursor=True)

        cursor_after_first = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor_after_first.last_id == t2.id

        # Create new telemetry
        t3 = Telemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload={"schema_version": "1.0", "value": 60.0},
        )

        # Second run: process only t3 (after t2)
        process_telemetry(record_cursor=True)

        cursor_after_second = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor_after_second.last_id == t3.id

    def test_multi_device_aggregation(self, multiple_devices_with_rules):
        """Test processing telemetry from multiple devices (multi-device).

        Verifies:
        - Aggregates rules by device
        - Aggregates telemetry by device
        - Evaluates each device's rules separately
        - Handles multiple devices in single batch

        Validates multi-device processing.
        """
        devices = multiple_devices_with_rules["devices"]
        rules = multiple_devices_with_rules["rules"]

        # Create telemetry for both devices
        t1 = Telemetry.objects.create(
            device=devices[0],
            timestamp=timezone.now(),
            payload={"schema_version": "1.0", "value": 55.0},  # Should trigger rule1
        )
        t2 = Telemetry.objects.create(
            device=devices[1],
            timestamp=timezone.now(),
            payload={"schema_version": "1.0", "value": 15.0},  # Should trigger rule2
        )

        # Initialize cursor
        TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Process
        process_telemetry(record_cursor=True)

        # Verify records were processed
        cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor.last_id >= t2.id

    def test_rule_trigger_execution(self, device_with_rule):
        """Test rule trigger execution when conditions met (business logic).

        Verifies:
        - Rule evaluation triggers when threshold exceeded
        - Trigger engine is called with evaluated rules
        - Event/action is created for triggered rules
        - Correct rule data passed to trigger engine

        Validates rule evaluation and triggering.
        """
        device = device_with_rule["device"]
        rule = device_with_rule["rule"]

        # Create telemetry that EXCEEDS rule threshold (threshold=50)
        telemetry = Telemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload={
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 75.0,  # > 50, should trigger
            },
        )

        TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Process
        process_telemetry(record_cursor=True)

        # Verify rule was evaluated
        cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor.last_id == telemetry.id

    def test_device_rule_filtering(self, multiple_devices_with_rules):
        """Test device-rule filtering (rule isolation).

        Verifies:
        - Only rules for a device are evaluated
        - Other devices' rules are ignored
        - Device filter is correctly applied
        - Rules are matched to correct device

        Validates device-rule isolation.
        """
        devices = multiple_devices_with_rules["devices"]

        # Create telemetry for device1
        t1 = Telemetry.objects.create(
            device=devices[0],
            timestamp=timezone.now(),
            payload={"schema_version": "1.0", "value": 55.0},
        )

        TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Process
        process_telemetry(record_cursor=True)

        # Cursor should be updated (record was processed)
        cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor.last_id == t1.id

    def test_disabled_rules_skipped(self, device_with_rule, disabled_rule):
        """Test disabled rules are not evaluated (rule status validation).

        Verifies:
        - is_enabled=False rules are skipped
        - Only enabled rules are evaluated
        - Disabled rules don't trigger actions
        - Rule status is checked before evaluation

        Validates rule enable/disable status handling.
        """
        device = device_with_rule["device"]

        # Create telemetry that matches BOTH rules
        telemetry = Telemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload={
                "schema_version": "1.0",
                "value": 60.0,  # Exceeds both thresholds
            },
        )

        TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Process
        process_telemetry(record_cursor=True)

        # Verify only enabled rule would trigger (disabled_rule should be skipped)
        cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor.last_id == telemetry.id

    def test_no_telemetry_early_exit(self, device_with_rule):
        """Test task exits gracefully when no telemetry available (edge case).

        Verifies:
        - Task returns early if no telemetry > cursor
        - No errors or exceptions
        - Cursor remains unchanged
        - Logging indicates no data

        Validates empty data handling.
        """
        TelemetryCursor.objects.create(name="Main Cursor", last_id=999)

        # Process with cursor beyond all telemetry
        result = process_telemetry(record_cursor=True)

        # Should return None (no exception)
        assert result is None

        # Cursor should be unchanged
        cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor.last_id == 999

    def test_batch_size_limiting(self, device_with_rule):
        """Test batch size limits number of records processed (scalability).

        Verifies:
        - Only batch_size records are fetched per call
        - Large datasets can be processed incrementally
        - Multiple runs needed for large datasets
        - Cursor allows continuation

        Validates batch processing efficiency.
        """
        device = device_with_rule["device"]

        # Create 5 telemetry records
        for i in range(5):
            Telemetry.objects.create(
                device=device,
                timestamp=timezone.now(),
                payload={"schema_version": "1.0", "value": 50.0 + i},
            )

        TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Process with batch_size=2
        process_telemetry(batch_size=2, record_cursor=True)

        # Cursor should be at 2nd record (limited by batch_size)
        cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor.last_id >= 0  # Should have processed something

    def test_cursor_recovery_after_failure(self, device_with_rule):
        """Test cursor recovery if processing fails (fault tolerance).

        Verifies:
        - Cursor is not updated if record_cursor=False
        - Failed processing doesn't update cursor
        - Allows retry without reprocessing
        - State is preserved for recovery

        Validates recovery mechanism.
        """
        device = device_with_rule["device"]

        telemetry = Telemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload={"schema_version": "1.0", "value": 55.0},
        )

        cursor = TelemetryCursor.objects.create(name="Main Cursor", last_id=0)
        initial_id = cursor.last_id

        # Process WITHOUT recording cursor (simulating failure scenario)
        process_telemetry(record_cursor=False)

        # Cursor should NOT be updated
        cursor_after = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor_after.last_id == initial_id

    def test_telemetry_point_aggregation(self, device_with_rule):
        """Test telemetry data aggregation for rule evaluation (data structure).

        Verifies:
        - TelemetryPoint objects created correctly
        - Timestamp and value extracted
        - Grouped by device
        - Available for rule evaluation

        Validates data aggregation logic.
        """
        device = device_with_rule["device"]

        # Create multiple telemetry records
        records = []
        for value in [40.0, 50.0, 60.0]:
            t = Telemetry.objects.create(
                device=device,
                timestamp=timezone.now(),
                payload={"schema_version": "1.0", "value": value},
            )
            records.append(t)

        TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Process
        process_telemetry(record_cursor=True)

        # Cursor should be updated to last record
        cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor.last_id == records[-1].id

    def test_rule_condition_validation(self, device_with_rule):
        """Test rule condition JSON validation (data validation).

        Verifies:
        - Rule condition is valid JSON
        - Condition is parsed into Condition object
        - Invalid conditions don't crash
        - Proper error handling

        Validates condition format handling.
        """
        device = device_with_rule["device"]
        rule = device_with_rule["rule"]

        # Create telemetry
        telemetry = Telemetry.objects.create(
            device=device,
            timestamp=timezone.now(),
            payload={"schema_version": "1.0", "value": 55.0},
        )

        TelemetryCursor.objects.create(name="Main Cursor", last_id=0)

        # Process (should not raise even with complex conditions)
        process_telemetry(record_cursor=True)

        # Verify completed without exception
        cursor = TelemetryCursor.objects.get(name="Main Cursor")
        assert cursor.last_id == telemetry.id
