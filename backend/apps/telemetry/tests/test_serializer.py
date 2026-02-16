import pytest
from datetime import datetime
from django.core.exceptions import ValidationError
from apps.telemetry.models import Telemetry
from apps.telemetry.serializer import TelemetrySerializer


@pytest.mark.django_db
class TestTelemetrySerializer:

    def test_validate_required_fields(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert cleaned["device"] == device
        assert cleaned["payload"]["schema_version"] == "1.0"
        assert cleaned["payload"]["serial_number"] == device.serial_number

    def test_validate_missing_serial_number(self):
        data = {"schema_version": "1.0"}

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "serial_number" in exc_info.value.message_dict

    def test_validate_missing_schema_version(self, device):
        data = {"serial_number": device.serial_number}

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "schema_version" in exc_info.value.message_dict

    def test_validate_unsupported_schema_version(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "999.0",
        }

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "schema_version" in exc_info.value.message_dict
        assert "Unsupported" in str(exc_info.value.message_dict["schema_version"])

    def test_validate_nonexistent_device(self):
        data = {
            "serial_number": "NONEXISTENT123",
            "schema_version": "1.0",
        }

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "device" in exc_info.value.message_dict
        assert "Invalid device" in str(exc_info.value.message_dict["device"])

    def test_normalize_value_int(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "value": 4200,
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert cleaned["payload"]["value"] == 42.0
        assert isinstance(cleaned["payload"]["value"], float)

    def test_normalize_value_float(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "value": 4250,
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert cleaned["payload"]["value"] == 42.5

    def test_normalize_value_string(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "value": "12345",
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert cleaned["payload"]["value"] == 123.45

    def test_normalize_value_invalid(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "value": "not_a_number",
        }

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "value" in exc_info.value.message_dict

    def test_parse_timestamp_string(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "timestamp": "2024-01-15T10:30:00Z",
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert "timestamp" in cleaned
        assert isinstance(cleaned["timestamp"], datetime)

    def test_parse_timestamp_invalid(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "timestamp": "not-a-timestamp",
        }

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "timestamp" in exc_info.value.message_dict

    def test_save_creates_telemetry(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
            "value": 4250,
        }

        serializer = TelemetrySerializer(data=data)
        telemetry = serializer.save()

        assert telemetry.id is not None
        assert telemetry.device == device
        assert telemetry.payload["schema_version"] == "1.0"
        assert telemetry.payload["serial_number"] == device.serial_number
        assert telemetry.payload["value"] == 42.5

    def test_save_with_serial_number(self, device):
        data = {
            "serial_number": device.serial_number,
            "schema_version": "1.0",
        }

        serializer = TelemetrySerializer(data=data)
        telemetry = serializer.save()

        assert telemetry.payload["serial_number"] == device.serial_number

    def test_to_dict(self, device):
        telemetry = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0", "value": 42.5}
        )

        serializer = TelemetrySerializer(instance=telemetry)
        result = serializer.to_dict()

        assert result["id"] == telemetry.id
        assert result["device_id"] == str(device.id)
        assert result["payload"]["schema_version"] == "1.0"
        assert result["payload"]["value"] == 42.5
        assert "timestamp" in result
