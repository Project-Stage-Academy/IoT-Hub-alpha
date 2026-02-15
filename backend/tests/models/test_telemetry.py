import pytest
from datetime import timedelta

from django.utils import timezone

from apps.telemetry.models import Telemetry


@pytest.mark.django_db
def test_create_telemetry(telemetry_factory, device):
    telemetry = telemetry_factory()

    assert telemetry.pk is not None
    assert telemetry.device == device
    assert "value" in telemetry.payload
    assert Telemetry.objects.count() == 1


@pytest.mark.django_db
def test_telemetry_str(telemetry_factory):
    telemetry = telemetry_factory()

    text = str(telemetry)
    assert str(telemetry.id) in text
    assert telemetry.device.name in text


@pytest.mark.django_db
def test_telemetry_ordering(telemetry_factory):
    first = telemetry_factory()
    second = telemetry_factory()

    first.timestamp = timezone.now() - timedelta(seconds=10)
    first.save(update_fields=["timestamp"])

    assert Telemetry.objects.first() == second
    assert Telemetry.objects.last() == first


@pytest.mark.django_db
def test_telemetry_deleted_when_device_deleted(telemetry_factory, device):
    telemetry_factory()

    device.delete()

    assert Telemetry.objects.count() == 0
