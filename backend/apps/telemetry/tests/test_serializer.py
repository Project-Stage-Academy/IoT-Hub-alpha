import pytest
from datetime import datetime
from django.core.exceptions import ValidationError
from apps.devices.models import Device, DeviceType
from apps.telemetry.models import Telemetry
from apps.telemetry.serializer import TelemetrySerializer


@pytest.fixture
def device_type(db):
    return DeviceType.objects.create(
        name="Temperature Sensor",
        metric_name="temperature",
        metric_unit="Celsius",
        metric_min="-40.0",
        metric_max="125.0",
    )


@pytest.fixture
def device(db, device_type):
    return Device.objects.create(
        name="Test Device",
        serial_number="TEST123456",
        device_type=device_type,
        location="Workshop 1",
        status="active",
    )


@pytest.mark.django_db
class TestTelemetrySerializer:

    def test_validate_required_fields(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {"test": "data"},
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert cleaned["device"] == device
        assert cleaned["payload"]["schema_version"] == "0.0.1"
        assert cleaned["payload"]["test"] == "data"

    def test_validate_missing_device_id(self):
        data = {"schema_version": "0.0.1", "payload": {}}

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "device_id" in exc_info.value.message_dict

    def test_validate_missing_schema_version(self, device):
        data = {"device_id": str(device.id), "payload": {}}

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "schema_version" in exc_info.value.message_dict

    def test_validate_missing_payload(self, device):
        data = {"device_id": str(device.id), "schema_version": "0.0.1"}

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "payload" in exc_info.value.message_dict

    def test_validate_nonexistent_device(self):
        data = {
            "device_id": "00000000-0000-0000-0000-000000000000",
            "schema_version": "0.0.1",
            "payload": {},
        }

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "device_id" in exc_info.value.message_dict
        assert "does not exist" in str(exc_info.value.message_dict["device_id"])

    def test_normalize_value_int(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {},
            "value": 42,
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert cleaned["payload"]["value"] == 42.0
        assert isinstance(cleaned["payload"]["value"], float)

    def test_normalize_value_float(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {},
            "value": 42.5,
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert cleaned["payload"]["value"] == 42.5

    def test_normalize_value_string(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {},
            "value": "123.45",
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert cleaned["payload"]["value"] == 123.45

    def test_normalize_value_invalid(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {},
            "value": "not_a_number",
        }

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "value" in exc_info.value.message_dict

    def test_parse_timestamp_string(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {},
            "timestamp": "2024-01-15T10:30:00Z",
        }

        serializer = TelemetrySerializer(data=data)
        cleaned = serializer.validate()

        assert "timestamp" in cleaned
        assert isinstance(cleaned["timestamp"], datetime)

    def test_parse_timestamp_invalid(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {},
            "timestamp": "not-a-timestamp",
        }

        serializer = TelemetrySerializer(data=data)

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate()

        assert "timestamp" in exc_info.value.message_dict

    def test_save_creates_telemetry(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {"test": "value"},
            "value": 42.5,
        }

        serializer = TelemetrySerializer(data=data)
        telemetry = serializer.save()

        assert telemetry.id is not None
        assert telemetry.device == device
        assert telemetry.payload["schema_version"] == "0.0.1"
        assert telemetry.payload["test"] == "value"
        assert telemetry.payload["value"] == 42.5

    def test_save_with_serial_number(self, device):
        data = {
            "device_id": str(device.id),
            "schema_version": "0.0.1",
            "payload": {},
            "serial_number": "SN123456",
        }

        serializer = TelemetrySerializer(data=data)
        telemetry = serializer.save()

        assert telemetry.payload["serial_number"] == "SN123456"

    def test_to_dict(self, device):
        telemetry = Telemetry.objects.create(
            device=device, payload={"schema_version": "0.0.1", "value": 42.5}
        )

        serializer = TelemetrySerializer(instance=telemetry)
        result = serializer.to_dict()

        assert result["id"] == telemetry.id
        assert result["device_id"] == str(device.id)
        assert result["payload"]["schema_version"] == "0.0.1"
        assert result["payload"]["value"] == 42.5
        assert "timestamp" in result
