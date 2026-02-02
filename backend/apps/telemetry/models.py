from django.db import models
from django.contrib.postgres.indexes import GinIndex

from apps.devices.models import Device


class Telemetry(models.Model):
    id = models.BigAutoField(primary_key=True)
    device = models.ForeignKey(
        Device, on_delete=models.CASCADE, related_name="telemetry_data"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    payload = models.JSONField(
        help_text=(
            'Schema: {"version": "0.0.1", "serial_number": "SN123456", ' '"value": 5.2}'
        )
    )

    class Meta:
        db_table = "telemetry"
        ordering = ["-timestamp"]
        indexes = [
            # Composite index for device + timestamp queries (most common pattern)
            models.Index(
                fields=["device", "-timestamp"], name="idx_telemetry_device_time"
            ),
            # Index for timestamp range queries
            models.Index(fields=["-timestamp"], name="idx_telemetry_timestamp"),
            # GIN index for JSONB payload queries
            GinIndex(fields=["payload"], name="idx_telemetry_payload_gin"),
        ]
        verbose_name_plural = "Telemetry"

    def __str__(self):
        return f"Telemetry {self.id} - {self.device.name} at {self.timestamp}"
