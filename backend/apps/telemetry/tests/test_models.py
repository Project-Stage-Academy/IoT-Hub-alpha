import pytest
from apps.telemetry.models import Telemetry


@pytest.mark.django_db
class TestTelemetryModel:
    def test_create_telemetry(self, device):
        telemetry = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0", "value": 42.5}
        )

        assert telemetry.id is not None
        assert telemetry.device == device
        assert telemetry.payload["schema_version"] == "1.0"
        assert telemetry.payload["value"] == 42.5
        assert telemetry.timestamp is not None

    def test_telemetry_str_representation(self, device):
        telemetry = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0"}
        )

        str_repr = str(telemetry)
        assert "Telemetry" in str_repr
        assert device.name in str_repr

    def test_telemetry_ordering(self, device):
        t1 = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0", "value": 1}
        )
        t2 = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0", "value": 2}
        )
        t3 = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0", "value": 3}
        )

        telemetry_list = list(Telemetry.objects.all())
        assert telemetry_list[0] == t3
        assert telemetry_list[1] == t2
        assert telemetry_list[2] == t1

    def test_telemetry_device_cascade_delete(self, device):
        telemetry = Telemetry.objects.create(
            device=device, payload={"schema_version": "1.0"}
        )

        telemetry_id = telemetry.id

        device.delete()

        assert not Telemetry.objects.filter(id=telemetry_id).exists()
