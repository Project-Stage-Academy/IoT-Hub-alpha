from django.db import models
from django.contrib.postgres.indexes import GinIndex

from apps.devices.models import Device


class TelemetrySchema(models.Model):
    """
    Save validation rules (jsonschema) and transformation rules for
    different telemetry versions.
    """

    version = models.CharField(
        max_length=50, unique=True, help_text="Example: '1.0', '2.0'"
    )

    validation_schema = models.JSONField(
        default=dict,
        help_text="Official JSON Schema for validating incoming telemetry data.",
    )

    transformation_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Rules for normalizing telemetry data."
        'Example: {"rename": {"val": "temperature"}}',
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "telemetry_schema"
        verbose_name_plural = "Telemetry Schemas"

    def __str__(self):
        return f"Schema v{self.version}"


class Telemetry(models.Model):
    id = models.BigAutoField(primary_key=True)
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="telemetry_data"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(
        help_text=(
            'Schema: {"schema_version": "1.0", "serial_number": "SN123456", '
            '"value": 5.2}'
        )
    )

    class Meta:
        db_table = "telemetry"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(
                fields=["device", "-timestamp"], name="idx_telemetry_device_time"
            ),
            models.Index(fields=["-timestamp"], name="idx_telemetry_timestamp"),
            GinIndex(fields=["payload"], name="idx_telemetry_payload_gin"),
        ]
        verbose_name_plural = "Telemetry"

    def __str__(self):
        return f"Telemetry {self.id} - {self.device.name} at {self.timestamp}"
