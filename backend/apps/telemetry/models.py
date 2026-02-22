from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from jsonschema import Draft7Validator, exceptions as jsonschema_exceptions

from apps.devices.models import Device


def validate_json_schema(value):
    """Validator to ensure the provided JSON is a valid JSON Schema."""
    if not isinstance(value, dict):
        raise ValidationError("JSON Schema must be a dictionary.")

    try:
        Draft7Validator.check_schema(value)
    except jsonschema_exceptions.SchemaError as e:
        raise ValidationError(f"Invalid JSON Schema: {e.message}")


def validate_transformation_rules(value):
    """Validator to ensure transformation rules have the correct structure."""
    if not isinstance(value, dict):
        raise ValidationError("Transformation rules must be a dictionary.")

    allowed_keys = {"rename", "multiply", "round"}

    for rule_key, rules in value.items():
        if rule_key not in allowed_keys:
            raise ValidationError(
                f"Invalid transformation rule key: '{rule_key}'. "
                f"Allowed keys are: {', '.join(allowed_keys)}."
            )

        if not isinstance(rules, dict):
            raise ValidationError(
                f"The value for '{rule_key}' must be a dictionary of field mappings."
            )

        for field, param in rules.items():
            if rule_key == "rename" and not isinstance(param, str):
                raise ValidationError(
                    f"Rename rule for '{field}' must be a string, got "
                    f"{type(param).__name__}."
                )
            elif rule_key in ("multiply", "round") and not isinstance(
                param, (int, float)
            ):
                raise ValidationError(
                    f"Rule '{rule_key}' for '{field}' must be a number, got "
                    f"{type(param).__name__}."
                )


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
        validators=[validate_json_schema],
        help_text="Official JSON Schema for validating incoming telemetry data.",
    )

    transformation_rules = models.JSONField(
        default=dict,
        blank=True,
        validators=[validate_transformation_rules],
        help_text=(
            "Rules for normalizing telemetry data. "
            'Example: {"rename": {"val": "temperature"}}'
        ),
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
