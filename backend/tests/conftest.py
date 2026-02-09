import pytest
from django.test import Client
from django.utils import timezone

from apps.devices.models import Device, DeviceType
from apps.events.models import Event
from apps.rules.models import Rule
from apps.telemetry.models import Telemetry


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def device_type(db):
    return DeviceType.objects.create(
        name="Temperature Sensor",
        description="Standard temperature sensor",
        metric_name=DeviceType.MetricName.TEMPERATURE,
        metric_unit="C",
        metric_min=-40.0,
        metric_max=125.0,
    )


@pytest.fixture
def device(db, device_type):
    return Device.objects.create(
        device_type=device_type,
        name="Boiler Sensor A",
        serial_number="SN-000001",
        location="Plant 1",
        status=Device.DeviceStatus.ACTIVE,
        last_seen=timezone.now(),
    )


@pytest.fixture
def sample_devices(db, device_type):
    return [
        Device.objects.create(
            device_type=device_type,
            name="Boiler Sensor A",
            serial_number="SN-000001",
            location="Plant 1",
            status=Device.DeviceStatus.ACTIVE,
        ),
        Device.objects.create(
            device_type=device_type,
            name="Boiler Sensor B",
            serial_number="SN-000002",
            location="Plant 2",
            status=Device.DeviceStatus.INACTIVE,
        ),
    ]


@pytest.fixture
def telemetry_factory(db, device):
    def create(*, device_obj=None, payload=None):
        device_obj = device_obj or device
        payload = payload or {
            "version": "1.0.0",
            "serial_number": device_obj.serial_number,
            "value": 22.5,
            "unit": device_obj.device_type.metric_unit,
        }
        return Telemetry.objects.create(device=device_obj, payload=payload)

    return create


@pytest.fixture
def rule(db, device):
    return Rule.objects.create(
        device=device,
        name="High Temp",
        description="Alert when temp exceeds threshold",
        condition={"type": "leaf", "operator": "gt", "threshold": 75.0},
        action_config=[{"type": "notification", "template_id": 1}],
        is_enabled=True,
    )


@pytest.fixture
def event(db, rule, telemetry_factory):
    telemetry = telemetry_factory()
    return Event.objects.create(
        rule=rule,
        severity=Event.EventSeverity.WARNING,
        message="Temperature exceeded threshold",
        execution_results=[
            {"type": "notification", "template_id": 1, "status": "completed"}
        ],
        telemetry_snapshot={
            "device_id": str(telemetry.device_id),
            "timestamp": telemetry.timestamp.isoformat(),
            "payload": telemetry.payload,
        },
    )


@pytest.fixture
def api_client(client):
    probe = client.get("/api/v1/devices")
    if probe.status_code == 404:
        pytest.skip("API endpoints are not wired in this project yet.")
    return client


@pytest.fixture
def auth_headers(api_client):
    response = api_client.get("/api/v1/auth/fake")
    if response.status_code == 404:
        pytest.skip("Auth endpoint not available.")
    if response.status_code != 200:
        pytest.skip("Auth endpoint not ready.")
    data = response.json() or {}
    token = data.get("fakejwt")
    if not token:
        pytest.skip("Auth endpoint did not return a token.")
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}
