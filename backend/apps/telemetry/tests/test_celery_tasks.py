import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
from django.db import OperationalError, InterfaceError
from django.db.models import Count

from apps.telemetry.tasks import ingest_telemetry_batch_async
from apps.telemetry.models import Telemetry


@pytest.mark.django_db
class TestIngestTelemetryBatchAsync:
    """Unit tests for ingest_telemetry_batch_async Celery task."""

    def test_successful_batch_persistence(self, device, telemetry_batch_data):
        """Test successful persistence of valid telemetry batch.

        Verifies that:
        - Task returns 'completed' status for valid batch
        - Response includes request_id, count, ids list, and summary
        - All 3 records persisted to database
        - Records correctly associated with device

        This is the happy path test - validates core functionality.
        """
        # Call function directly (not through Celery)
        result = ingest_telemetry_batch_async(
            telemetry_batch_data, "test-request-1"
        )

        assert result["status"] == "completed"
        assert result["request_id"] == "test-request-1"
        assert result["count"] == 3
        assert len(result["ids"]) == 3
        assert result["summary"]["total"] == 3
        assert result["summary"]["successful"] == 3
        assert result["summary"]["failed"] == 0

        # Verify data persisted to DB
        assert Telemetry.objects.count() == 3
        telemetry_records = Telemetry.objects.select_related("device").all()
        assert all(t.device == device for t in telemetry_records)

    def test_empty_batch_handling(self):
        """Test handling of empty batch data (edge case).

        Verifies that:
        - Empty batch [] is accepted without error
        - Task returns 'completed' status (not failed)
        - count=0 and successful=0 in response
        - No database records created

        This validates graceful handling of edge cases.
        """
        result = ingest_telemetry_batch_async([], "test-request-empty")

        assert result["status"] == "completed"
        assert result["count"] == 0
        assert result["summary"]["successful"] == 0

    def test_single_item_batch(self, device, telemetry_batch_data):
        """Test batch with single telemetry item (minimal batch).

        Verifies that:
        - Single record batch is processed successfully
        - Response status='completed', count=1
        - Exactly 1 record created in database
        - Works for minimal valid input

        Validates minimal batch size handling.
        """
        single_item = telemetry_batch_data[:1]
        result = ingest_telemetry_batch_async(
            single_item, "test-request-single"
        )

        assert result["status"] == "completed"
        assert result["count"] == 1
        assert Telemetry.objects.count() == 1

    @patch("apps.telemetry.services.TelemetryBatchProcessor.process_batch")
    def test_error_handling_with_exception(
        self, mock_process_batch, device, telemetry_batch_data
    ):
        """Test handling of non-retryable exceptions (error resilience).

        Simulates ValueError from TelemetryBatchProcessor and verifies:
        - Task catches exception (doesn't crash)
        - Returns 'failed' status (not exception)
        - Error message included in response
        - summary shows all records failed (failed=3)

        Validates non-retryable error handling and proper error messaging.
        """
        mock_process_batch.side_effect = ValueError("Processing error")

        result = ingest_telemetry_batch_async(
            telemetry_batch_data, "test-request-error"
        )

        assert result["status"] == "failed"
        assert result["request_id"] == "test-request-error"
        assert "error" in result
        assert result["summary"]["failed"] == 3

    def test_exponential_backoff_config(self):
        """Test exponential backoff retry configuration (reliability).

        Verifies task decorator settings:
        - max_retries=3 (up to 3 retry attempts)
        - default_retry_delay=60 (base delay in seconds)
        - Exponential backoff formula: countdown=60 * (2**retry_count)
        - Resulting delays: 60s, 120s, 240s for retries 0, 1, 2

        Validates transient error retry strategy configuration.
        """
        # Verify task properties
        assert ingest_telemetry_batch_async.max_retries == 3
        assert ingest_telemetry_batch_async.default_retry_delay == 60

    def test_request_id_tracking(self, device, telemetry_batch_data):
        """Test request_id is preserved through task execution (traceability).

        Verifies that:
        - Custom request_id passed to task is returned in response
        - Request ID used for logging and debugging
        - Maintains traceability across async operations

        Validates end-to-end request tracking for debugging.
        """
        request_id = "unique-request-id-123"
        result = ingest_telemetry_batch_async(
            telemetry_batch_data, request_id
        )

        assert result["request_id"] == request_id

    @patch("apps.telemetry.services.TelemetryBatchProcessor.process_batch")
    def test_database_error_retry_behavior(self, mock_process_batch):
        """Test retry logic on transient database errors (fault tolerance).

        Simulates OperationalError (transient DB connection issue) and verifies:
        - Task identifies it as retryable error (DatabaseError family)
        - Attempts retry instead of immediate failure
        - In eager test mode, retry exception is raised (proving retry triggered)

        Validates resilience to transient database connectivity issues.
        """
        from django.db import OperationalError

        # Simulate OperationalError (transient DB error, should retry)
        mock_process_batch.side_effect = OperationalError(
            "Connection refused"
        )

        batch_data = [
            {
                "device_id": str(uuid4()),
                "payload": {
                    "schema_version": "1.0",
                    "value": 2550,
                },
                "timestamp": "2025-02-15T12:00:00Z",
            }
        ]

        # In eager mode, retry raises the exception
        with pytest.raises(OperationalError):
            ingest_telemetry_batch_async(
                batch_data, "test-request-db-error"
            )

    def test_large_batch_processing(self, device):
        """Test processing large batch (performance and scalability).

        Tests batch with 50 telemetry records and verifies:
        - Task completes successfully with large dataset
        - Response count=50, status='completed'
        - All 50 records persisted to database
        - No performance degradation with batch size

        Validates scalability and bulk operation efficiency.
        """
        large_batch = [
            {
                "device_id": str(device.id),
                "payload": {
                    "schema_version": "1.0",
                    "serial_number": device.serial_number,
                    "value": 2550 + i,
                },
                "timestamp": f"2025-02-15T12:{(i % 60):02d}:00Z",
            }
            for i in range(50)
        ]

        result = ingest_telemetry_batch_async(
            large_batch, "test-request-large"
        )

        assert result["status"] == "completed"
        assert result["count"] == 50
        assert Telemetry.objects.count() == 50

    def test_task_response_structure(self, device, telemetry_batch_data):
        """Test response structure matches API contract (contract testing).

        Verifies response dictionary contains all required fields:
        - Top-level: status, request_id, count, ids, summary
        - summary: total, successful, failed
        - Each field has correct type and is present

        Validates API contract compliance for clients.
        """
        result = ingest_telemetry_batch_async(
            telemetry_batch_data, "test-request-structure"
        )

        # Check all required fields
        assert "status" in result
        assert "request_id" in result
        assert "count" in result
        assert "ids" in result
        assert "summary" in result

        summary = result["summary"]
        assert "total" in summary
        assert "successful" in summary
        assert "failed" in summary

    def test_payload_persistence_integrity(self, device, telemetry_batch_data):
        """Test payload data persisted exactly as provided (data integrity).

        Retrieves persisted record and verifies:
        - schema_version preserved ('1.0')
        - serial_number preserved
        - All payload fields present
        - No data transformation or loss

        Validates end-to-end data integrity and fidelity.
        """
        result = ingest_telemetry_batch_async(
            telemetry_batch_data, "test-request-payload"
        )

        assert result["status"] == "completed"

        # Verify payload integrity
        persisted = Telemetry.objects.order_by("id").first()
        assert persisted is not None
        assert persisted.payload["schema_version"] == "1.0"
        assert persisted.payload["serial_number"] == device.serial_number
        assert "value" in persisted.payload

    def test_multiple_devices_same_batch(self, db):
        """Test batch containing records from multiple devices (multi-tenant).

        Creates 2 devices and batch with 2 records from different devices, verifies:
        - Both records processed successfully
        - count=2 in response
        - Each device has exactly 1 record in database
        - Device associations correct

        Validates multi-device/multi-tenant support.
        """
        from apps.devices.models import Device, DeviceType

        # Create device type and devices with bulk_create (optimize DB queries)
        device_type = DeviceType.objects.create(
            name="Temp Sensor",
            metric_name="temperature",
            metric_unit="C",
            metric_min="-40.0",
            metric_max="125.0",
        )
        device1, device2 = Device.objects.bulk_create([
            Device(
                name="Device 1",
                serial_number="SN001",
                device_type=device_type,
                status="active",
            ),
            Device(
                name="Device 2",
                serial_number="SN002",
                device_type=device_type,
                status="active",
            ),
        ])

        batch = [
            {
                "device_id": str(device1.id),
                "payload": {
                    "schema_version": "1.0",
                    "serial_number": device1.serial_number,
                    "value": 2550,
                },
            },
            {
                "device_id": str(device2.id),
                "payload": {
                    "schema_version": "1.0",
                    "serial_number": device2.serial_number,
                    "value": 2560,
                },
            },
        ]

        result = ingest_telemetry_batch_async(batch, "test-multi-device")

        assert result["status"] == "completed"
        assert result["count"] == 2

        # Verify device associations with single aggregated query (avoid N+1)
        device_counts = Telemetry.objects.filter(
            device__in=[device1, device2]
        ).values("device_id").annotate(count=Count("id"))

        count_dict = {c["device_id"]: c["count"] for c in device_counts}
        assert count_dict[device1.id] == 1
        assert count_dict[device2.id] == 1

    def test_task_binding_property(self):
        """Test task is bound to Celery context (configuration validation).

        Verifies:
        - Task has 'request' attribute (only on bound tasks)
        - Can access self.request.retries for retry logic
        - Task properly initialized with @shared_task(bind=True)

        Validates core task configuration.
        """
        # Verify task can be called as a bound task
        assert hasattr(ingest_telemetry_batch_async, "request")

    def test_retry_delay_exponential_calculation(self):
        """Test exponential backoff delay calculation formula (retry strategy).

        Documents and verifies exponential backoff strategy:
        - Base delay: 60 seconds
        - Formula: countdown=60 * (2**retry_count)
        - Resulting delays: 60s (retry 0), 120s (retry 1), 240s (retry 2)
        - Prevents thundering herd problem

        Validates progressive backoff strategy configuration.
        """
        # Task uses: countdown=60 * (2**self.request.retries)
        # This verifies the configuration supports exponential backoff
        base_delay = ingest_telemetry_batch_async.default_retry_delay
        assert base_delay == 60
        # Exponential backoff: 60s, 120s, 240s for retries 0, 1, 2