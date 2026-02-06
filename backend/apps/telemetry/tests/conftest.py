import pytest
from django.test import Client
from apps.devices.models import Device, DeviceType


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


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def sync_mode(settings):
    settings.TELEMETRY_ASYNC_INGESTION = False
    yield


@pytest.fixture
def async_mode(settings):
    settings.TELEMETRY_ASYNC_INGESTION = True
    yield
