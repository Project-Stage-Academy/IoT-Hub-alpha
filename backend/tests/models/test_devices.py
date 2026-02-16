import pytest
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError

from apps.devices.models import Device, DeviceType
from tests.factories import DeviceFactory, DeviceTypeFactory


@pytest.mark.django_db
def test_create_device():
    device_name = "Device name"

    device = DeviceFactory(name=device_name)

    assert device.pk is not None
    assert device.name == device_name
    assert device.device_type is not None
    assert device.serial_number
    assert device.status == Device.DeviceStatus.ACTIVE
    assert Device.objects.count() == 1


@pytest.mark.django_db
def test_device_str():
    device = DeviceFactory(name="Pump Sensor", serial_number="SN-000123")

    assert str(device) == "Pump Sensor (SN-000123)"


@pytest.mark.django_db
def test_device_type_str():
    device_type = DeviceTypeFactory(name="Temp Sensor", metric_name="temperature")

    assert str(device_type) == "Temp Sensor (temperature)"


@pytest.mark.django_db
def test_device_type_clean_rejects_invalid_min_max():
    device_type = DeviceTypeFactory(metric_min=10.0, metric_max=5.0)

    with pytest.raises(ValidationError) as excinfo:
        device_type.full_clean()

    errors = excinfo.value.message_dict
    assert "metric_min" in errors
    assert "metric_max" in errors


@pytest.mark.django_db
def test_device_type_clean_allows_missing_min_or_max():
    device_type_only_min = DeviceTypeFactory(metric_min=1.0, metric_max=None)
    device_type_only_max = DeviceTypeFactory(metric_min=None, metric_max=100.0)

    device_type_only_min.full_clean()
    device_type_only_max.full_clean()


@pytest.mark.django_db
def test_device_type_metric_name_choices():
    choices = {choice for choice, _label in DeviceType.MetricName.choices}

    assert {"vibration", "temperature", "pressure"} <= choices


@pytest.mark.django_db
def test_device_type_delete_protects_devices():
    device = DeviceFactory()
    device_type = device.device_type

    with pytest.raises(ProtectedError):
        device_type.delete()
