import uuid

from django.db import models


class DeviceType(models.Model):
    class MetricName(models.TextChoices):
        VIBRATION = "vibration", "Vibration"
        TEMPERATURE = "temperature", "Temperature"
        PRESSURE = "pressure", "Pressure"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    metric_name = models.CharField(
        max_length=20, 
        choices=MetricName.choices,
        help_text="Primary metric this device type measures"
    )
    metric_unit = models.CharField(max_length=50, help_text="Unit of measurement")
    metric_min = models.DecimalField(
        max_digits=15, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Minimum expected value"
    )
    metric_max = models.DecimalField(
        max_digits=15, 
        decimal_places=4, 
        null=True, 
        blank=True,
        help_text="Maximum expected value"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "device_types"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="idx_device_type_name"),
            models.Index(fields=["metric_name"], name="idx_device_type_metric")
        ]

    def __str__(self):
        return f"{self.name} ({self.metric_name})"


class Device(models.Model):
    class DeviceStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_type = models.ForeignKey(
        DeviceType,
        on_delete=models.PROTECT,
        related_name="devices",
        help_text="Device type reference"
    )
    name = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=100, unique=True)
    location = models.TextField(
        blank=True,
        null=True,
        help_text="Machine ID, Industrial workshop number"
    )
    status = models.CharField(
        max_length=20,
        choices=DeviceStatus.choices,
        default=DeviceStatus.ACTIVE
    )
    last_seen = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last telemetry received timestamp"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "devices"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["serial_number"], name="idx_device_serial"),
            models.Index(fields=["device_type"], name="idx_device_type"),
            models.Index(fields=["status", "last_seen"], name="idx_device_status_last_seen")
        ]

    def __str__(self):
        return f"{self.name} ({self.serial_number})"
