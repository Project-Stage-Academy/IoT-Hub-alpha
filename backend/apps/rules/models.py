import uuid

from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError

from apps.devices.models import Device


def validate_action_config(value):
    """Validates action_config JSON structure."""
    if not isinstance(value, list):
        raise ValidationError("action_config must be a list of action items")

    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each action item must be a dictionary")

        if "type" not in item:
            raise ValidationError("Each action item must have a 'type' field")

        cooldown_minutes = item.get("cooldown_minutes")
        if cooldown_minutes is not None:
            if not isinstance(cooldown_minutes, int):
                raise ValidationError("cooldown_minutes must be an integer")
            if cooldown_minutes < 0:
                raise ValidationError("cooldown_minutes must be >= 0")

        action_type = item.get("type")

        # Type-specific validation
        if action_type == "notification":
            if "template_id" not in item:
                raise ValidationError("Notification action must include template_id")
        elif action_type == "stop_machine":
            if "machine_id" not in item:
                raise ValidationError("stop_machine action must include machine_id")


class Rule(models.Model):
    class RuleOperator(models.TextChoices):
        GT = "gt", "Greater Than (>)"
        LT = "lt", "Less Than (<)"
        GTE = "gte", "Greater Than or Equal (>=)"
        LTE = "lte", "Less Than or Equal (<=)"
        EQ = "eq", "Equal (=)"
        NEQ = "neq", "Not Equal (!=)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="rules")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    comparison_operator = models.CharField(max_length=10, choices=RuleOperator.choices)
    threshold = models.DecimalField(max_digits=15, decimal_places=4)
    action_config = models.JSONField(
        validators=[validate_action_config],
        help_text=(
            'Schema: [{"type": "notification", "template_id": 5}, '
            '{"type": "stop_machine", "machine_id": "M-123"}]'
        ),
    )
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "rules"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["device", "is_enabled"], name="idx_rule_device_enabled"
            ),
            models.Index(fields=["is_enabled"], name="idx_rule_is_enabled"),
            models.Index(fields=["last_triggered_at"], name="idx_rule_last_triggered"),
            GinIndex(fields=["action_config"], name="idx_rule_action_config_gin"),
        ]

    def __str__(self):
        return f"{self.name} - {self.device.name}"
