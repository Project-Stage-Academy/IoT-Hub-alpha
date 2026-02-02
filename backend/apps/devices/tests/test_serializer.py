from django.test import TestCase

from apps.devices.models import DeviceType, Device
from apps.devices.serializer import (
    DeviceRepository,
    DeviceValidator,
    ApiValidationError,
)


class DeviceSerializerTests(TestCase):
    def setUp(self):
        self.dt = DeviceType.objects.create(
            name="Temp Sensor",
            metric_name=DeviceType.MetricName.TEMPERATURE,
            metric_unit="C",
        )

    def test_serializer_creates_device(self):
        payload = {
            "name": "Sensor 1",
            "serial_number": "SN-001",
            "device_type_id": str(self.dt.id),
            "status": "active",
            "location": "Lab",
        }
        cleaned = DeviceValidator(data=payload, partial=False).validate()
        d = DeviceRepository.save(cleaned)
        self.assertTrue(Device.objects.filter(id=d.id).exists())
        self.assertEqual(d.device_type_id, self.dt.id)

    def test_serializer_rejects_blank_name(self):
        payload = {
            "name": "",
            "serial_number": "SN-001",
            "device_type_id": str(self.dt.id),
        }
        with self.assertRaises(ApiValidationError) as ctx:
            DeviceValidator(data=payload, partial=False).validate()
        self.assertIn("name", ctx.exception.errors)

    def test_serializer_rejects_invalid_device_type_id(self):
        payload = {
            "name": "Sensor 1",
            "serial_number": "SN-001",
            "device_type_id": "00000000-0000-0000-0000-000000000000",
        }
        with self.assertRaises(ApiValidationError) as ctx:
            DeviceValidator(data=payload, partial=False).validate()
        self.assertIn("device_type_id", ctx.exception.errors)

    def test_serializer_rejects_invalid_status(self):
        payload = {
            "name": "Sensor 1",
            "serial_number": "SN-001",
            "device_type_id": str(self.dt.id),
            "status": "INVALID",  # не в choices
        }
        with self.assertRaises(ApiValidationError) as ctx:
            DeviceValidator(data=payload, partial=False).validate()
        self.assertIn("status", ctx.exception.errors)
