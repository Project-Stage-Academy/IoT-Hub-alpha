from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.devices.models import DeviceType, Device


class DeviceTypeModelTests(TestCase):
    def test_metric_min_must_be_less_than_metric_max(self):
        dt = DeviceType(
            name="DT-Temp",
            metric_name=DeviceType.MetricName.TEMPERATURE,
            metric_unit="C",
            metric_min=Decimal("10"),
            metric_max=Decimal("5"),
        )
        with self.assertRaises(ValidationError) as ctx:
            dt.full_clean()

        err = ctx.exception.message_dict
        self.assertIn("metric_min", err)
        self.assertIn("metric_max", err)


class DeviceModelTests(TestCase):
    def setUp(self):
        self.dt = DeviceType.objects.create(
            name="Temp Sensor",
            metric_name=DeviceType.MetricName.TEMPERATURE,
            metric_unit="C",
        )

    def test_device_status_must_be_in_choices(self):
        d = Device(
            device_type=self.dt,
            name="Sensor 1",
            serial_number="SN-001",
            status="not-valid",
        )
        with self.assertRaises(ValidationError) as ctx:
            d.full_clean()
        self.assertIn("status", ctx.exception.message_dict)

    def test_serial_number_must_be_unique(self):
        Device.objects.create(
            device_type=self.dt,
            name="Sensor 1",
            serial_number="SN-UNIQ",
        )

        d2 = Device(
            device_type=self.dt,
            name="Sensor 2",
            serial_number="SN-UNIQ",
        )
        with self.assertRaises(ValidationError) as ctx:
            d2.full_clean()
        self.assertIn("serial_number", ctx.exception.message_dict)
