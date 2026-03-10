import uuid
from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.devices.models import Device
from .services.data_structure import Condition


ALLOWED_ACTION_TYPES = {"notification", "stop_machine", "alert", "webhook", "command"}


def _validate_cooldown(item: dict) -> None:
    cooldown_minutes = item.get("cooldown_minutes")
    if cooldown_minutes is None:
        return
    if not isinstance(cooldown_minutes, int):
        raise DjangoValidationError("cooldown_minutes must be an integer")
    if cooldown_minutes < 0:
        raise DjangoValidationError("cooldown_minutes must be >= 0")


def _validate_action_type(action_type: str) -> None:
    if action_type not in ALLOWED_ACTION_TYPES:
        raise DjangoValidationError(
            "Unsupported action type. Allowed values: "
            "notification, stop_machine, alert, webhook, command"
        )


def _validate_type_specific_requirements(item: dict, action_type: str) -> None:
    required_fields = {
        "notification": "template_id",
        "alert": "template_id",
        "webhook": "url",
        "stop_machine": "machine_id",
        "command": "command",
    }
    required_field = required_fields.get(action_type)
    if required_field and required_field not in item:
        if action_type == "notification":
            raise DjangoValidationError("Notification action must include template_id")
        raise DjangoValidationError(
            f"{action_type} action must include {required_field}"
        )


def _validate_action_item(item: dict) -> None:
    if "type" not in item:
        raise DjangoValidationError("Each action item must have a 'type' field")
    _validate_cooldown(item)
    action_type = item["type"]
    _validate_action_type(action_type)
    _validate_type_specific_requirements(item, action_type)


def validate_action_config(value):
    """Validates action_config JSON structure."""
    if not isinstance(value, list):
        raise DjangoValidationError("action_config must be a list of action items")

    for item in value:
        if not isinstance(item, dict):
            raise DjangoValidationError("Each action item must be a dictionary")
        _validate_action_item(item)


def validate_condition(condition):
    try:
        Condition.model_validate(condition)
    except Exception as e:
        raise DjangoValidationError(str(e))


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
    condition = models.JSONField(
        validators=[validate_condition],
        help_text=(
            "Schema: [{{"
            '"type": "leaf", '
            '"operator": "gt", '
            '"threshold": 25.5, '
            '"occurrences": 3, '
            '"window_seconds": 60'
            "}]"
        ),
    )
    action_config = models.JSONField(
        validators=[validate_action_config],
        help_text=(
            'Schema: [{"type": "alert", "template_id": 5}, '
            '{"type": "webhook", "url": "https://ops.example/webhook"}, '
            '{"type": "command", "command": "set_device_status", '
            '"params": {"status": "inactive"}}]'
        ),
    )
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    event_cooldown_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when cooldown for event creation expires",
    )
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


class RuleAuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        ENABLE = "enable", "Enable"
        DISABLE = "disable", "Disable"

    class Source(models.TextChoices):
        SIGNAL = "signal", "Signal"
        ADMIN_ACTION = "admin_action", "Admin Action"
        API = "api", "API"
        SYSTEM = "system", "System"

    id = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rule_id = models.UUIDField(null=True, blank=True)
    action = models.CharField(max_length=32, choices=Action.choices)
    changed_fields = models.JSONField(default=list, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    actor_user_id = models.IntegerField(null=True, blank=True)
    actor_username = models.CharField(max_length=150, null=True, blank=True)
    request_id = models.CharField(max_length=128, null=True, blank=True)
    source = models.CharField(max_length=32, choices=Source.choices)

    class Meta:
        db_table = "rule_audit_log"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["created_at"], name="idx_r_audit_created_at"),
            models.Index(fields=["rule_id"], name="idx_r_audit_rule_id"),
            models.Index(
                fields=["action", "created_at"],
                name="idx_r_audit_action_created",
            ),
        ]

    def __str__(self) -> str:
        created = self.created_at.isoformat() if self.created_at else "unsaved"
        return f"{self.action} rule={self.rule_id} at {created}"
