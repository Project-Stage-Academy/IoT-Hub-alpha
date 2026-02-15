import pytest
import json
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


@pytest.fixture
def celery_config():
    """Configure Celery for testing (eager mode)."""
    return {
        "broker_url": "memory://",
        "result_backend": "cache+memory://",
        "task_always_eager": True,
        "task_eager_propagates": True,
    }


@pytest.fixture
def celery_app(celery_config):
    """Return configured Celery app for testing."""
    from celery import Celery

    app = Celery()
    app.config_from_object(celery_config)
    return app


@pytest.fixture
def telemetry_batch_data(device):
    """Valid telemetry batch data for testing (serialized format)."""
    return [
        {
            "device_id": str(device.id),
            "payload": {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 2550,
            },
            "timestamp": "2025-02-15T12:00:00Z",
        },
        {
            "device_id": str(device.id),
            "payload": {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 2560,
            },
            "timestamp": "2025-02-15T12:01:00Z",
        },
        {
            "device_id": str(device.id),
            "payload": {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 2570,
            },
            "timestamp": "2025-02-15T12:02:00Z",
        },
    ]
