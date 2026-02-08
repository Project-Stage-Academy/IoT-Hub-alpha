import pytest
from django.core.exceptions import ValidationError

from apps.telemetry.models import Telemetry
from apps.telemetry.services import (
    TelemetryValidator,
    TelemetryBatchProcessor,
    TelemetryResponseFormatter,
    extract_validation_errors,
)


@pytest.mark.django_db
class TestTelemetryValidatorSingle:
    """Tests for TelemetryValidator.validate_single."""

    def test_valid_single(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "value": 25.5,
        }
        validated, error = TelemetryValidator.validate_single(data)

        assert error is None
        assert validated is not None
        assert validated["device"] == device
        assert validated["payload"]["schema_version"] == "1.0"
        assert validated["payload"]["value"] == 25.5

    def test_missing_serial_number(self):
        data = {"schema_version": "1.0"}
        validated, error = TelemetryValidator.validate_single(data)

        assert validated is None
        assert error is not None
        assert "serial_number" in str(error)

    def test_missing_schema_version(self, device):
        data = {"serial_number": device.serial_number}
        validated, error = TelemetryValidator.validate_single(data)

        assert validated is None
        assert error is not None

    def test_invalid_schema_version(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "99.0",
        }
        validated, error = TelemetryValidator.validate_single(data)

        assert validated is None
        assert error is not None

    def test_nonexistent_device(self):
        data = {
            "serial_number": "NO-SUCH-DEVICE",
            "schema_version": "1.0",
        }
        validated, error = TelemetryValidator.validate_single(data)

        assert validated is None
        assert error is not None

    def test_with_timestamp(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "timestamp": "2025-06-15T12:00:00Z",
        }
        validated, error = TelemetryValidator.validate_single(data)

        assert error is None
        assert "timestamp" in validated

    def test_invalid_timestamp(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "timestamp": "not-a-date",
        }
        validated, error = TelemetryValidator.validate_single(data)

        assert validated is None
        assert error is not None


@pytest.mark.django_db
class TestTelemetryValidatorBatch:
    """Tests for TelemetryValidator.validate_batch."""

    def test_valid_batch(self, device):
        data = [
            {
                "serial_number": device.serial_number,
                "schema_version": "1.0",
                "value": 1.0,
            },
            {
                "serial_number": device.serial_number,
                "schema_version": "1.0",
                "value": 2.0,
            },
        ]
        validated, errors = TelemetryValidator.validate_batch(data)

        assert len(validated) == 2
        assert len(errors) == 0

    def test_batch_with_one_invalid(self, device):
        data = [
            {"serial_number": device.serial_number, "schema_version": "1.0"},
            {"schema_version": "1.0"},  # missing serial_number
        ]
        validated, errors = TelemetryValidator.validate_batch(data)

        assert len(validated) == 1
        assert len(errors) == 1
        assert errors[0]["index"] == 1

    def test_batch_all_invalid(self):
        data = [
            {"schema_version": "1.0"},
            {},
        ]
        validated, errors = TelemetryValidator.validate_batch(data)

        assert len(validated) == 0
        assert len(errors) == 2

    def test_empty_batch(self):
        validated, errors = TelemetryValidator.validate_batch([])

        assert len(validated) == 0
        assert len(errors) == 0


@pytest.mark.django_db
class TestTelemetryBatchProcessorSingle:
    """Tests for TelemetryBatchProcessor.process_single."""

    def test_process_single(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "value": 42.0,
        }
        validated, _ = TelemetryValidator.validate_single(data)
        telemetry = TelemetryBatchProcessor.process_single(validated)

        assert telemetry.id is not None
        assert telemetry.device == device
        assert Telemetry.objects.count() == 1

    def test_process_single_with_timestamp(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "timestamp": "2025-06-15T12:00:00Z",
        }
        validated, _ = TelemetryValidator.validate_single(data)
        telemetry = TelemetryBatchProcessor.process_single(validated)

        assert telemetry.id is not None


@pytest.mark.django_db
class TestTelemetryBatchProcessorBatch:
    """Tests for TelemetryBatchProcessor.process_batch."""

    def test_process_batch(self, device):
        items = [
            {"serial_number": device.serial_number, "schema_version": "1.0", "value": i}
            for i in range(5)
        ]
        validated, _ = TelemetryValidator.validate_batch(items)
        created = TelemetryBatchProcessor.process_batch(validated)

        assert len(created) == 5
        assert Telemetry.objects.count() == 5

    def test_process_batch_empty(self):
        created = TelemetryBatchProcessor.process_batch([])

        assert len(created) == 0
        assert Telemetry.objects.count() == 0


@pytest.mark.django_db
class TestTelemetryResponseFormatter:
    """Tests for response formatting helpers."""

    def test_format_single_created(self, device):
        telemetry = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0"}
        )
        resp = TelemetryResponseFormatter.format_single_created(telemetry)

        assert resp["status"] == "created"
        assert resp["id"] == telemetry.id
        assert resp["device_id"] == str(device.id)

    def test_format_single_created_with_idempotency(self, device):
        telemetry = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0"}
        )
        resp = TelemetryResponseFormatter.format_single_created(
            telemetry, idempotency_key="abc-123"
        )

        assert resp["idempotency_key"] == "abc-123"

    def test_format_batch_created(self, device):
        objs = [
            Telemetry.objects.create(device=device, payload={"schema_version": "1.0"})
            for _ in range(3)
        ]
        resp = TelemetryResponseFormatter.format_batch_created(objs, total=3)

        assert resp["status"] == "created"
        assert resp["count"] == 3
        assert len(resp["ids"]) == 3
        assert resp["summary"]["total"] == 3
        assert resp["summary"]["failed"] == 0

    def test_format_validation_error(self):
        errors = [{"error": "bad", "index": 0}]
        resp = TelemetryResponseFormatter.format_validation_error(
            errors, total=2, is_batch=True
        )

        assert "Batch ingestion failed" in resp["error"]
        assert resp["details"]["summary"]["total"] == 2
        assert resp["details"]["summary"]["failed"] == 1


class TestExtractValidationErrors:
    """Tests for the extract_validation_errors helper."""

    def test_with_message_dict(self):
        exc = ValidationError({"field": "error msg"})
        result = extract_validation_errors(exc)
        assert "field" in result

    def test_without_message_dict(self):
        exc = ValidationError("plain error")
        result = extract_validation_errors(exc)
        assert "error" in result
