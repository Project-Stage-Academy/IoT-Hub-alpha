import factory
from apps.devices.models import Device, DeviceType


class DeviceTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DeviceType

    name = factory.Sequence(lambda n: f"Device Type {n}")
    description = factory.Faker("sentence")
    metric_name = DeviceType.MetricName.TEMPERATURE
    metric_unit = "C"
    metric_min = -10.0
    metric_max = 120.0


class DeviceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Device

    device_type = factory.SubFactory(DeviceTypeFactory)
    name = factory.Faker("word")
    serial_number = factory.Sequence(lambda n: f"SN-{n:06d}")
    status = Device.DeviceStatus.ACTIVE
