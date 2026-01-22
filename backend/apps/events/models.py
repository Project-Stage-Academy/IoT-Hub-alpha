from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError

from apps.rules.models import Rule


def validate_execution_results(value):
    """Validates execution_results JSON structure."""
    if not isinstance(value, list):
        raise ValidationError("execution_results must be a list of execution items")

    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each execution result must be a dictionary")

        if "type" not in item:
            raise ValidationError("Each execution result must have a 'type' field")

        if "status" not in item:
            raise ValidationError("Each execution result must have a 'status' field")

        action_type = item.get("type")

        if action_type == "notification":
            if "template_id" not in item:
                raise ValidationError("Notification result must include template_id")
        elif action_type == "stop_machine":
            if "machine_id" not in item:
                raise ValidationError("stop_machine result must include machine_id")


def validate_telemetry_snapshot(value):
    """Validates telemetry snapshot JSON structure."""
    if value is None:
        return

    if not isinstance(value, dict):
        raise ValidationError("Telemetry snapshot must be a JSON object")

    # Optional: validate expected fields in telemetry snapshot
    if value and "payload" not in value:
        raise ValidationError("Telemetry snapshot should contain 'payload' field")


class Event(models.Model):
    class EventSeverity(models.TextChoices):
        CRITICAL = "critical", "Critical"
        WARNING = "warning", "Warning"
        INFO = "info", "Info"

    class EventStatus(models.TextChoices):
        NEW = "new", "New"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    id = models.BigAutoField(primary_key=True)
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name="events")
    timestamp = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=20, choices=EventSeverity.choices)
    message = models.TextField(help_text="Human-readable event description")
    execution_results = models.JSONField(
        validators=[validate_execution_results],
        help_text=(
            'Schema: [{"type": "notification", "template_id": 5, '
            '"status": "completed", "sent_count": 3, '
            '"completed_at": "2025-01-21T10:00:08Z"}, '
            '{"type": "stop_machine", "machine_id": "M-123", '
            '"status": "failed", "error": "API timeout"}]'
        ),
    )
    telemetry_snapshot = models.JSONField(
        validators=[validate_telemetry_snapshot],
        null=True,
        blank=True,
        help_text=(
            "Snapshot of telemetry data that triggered this event. "
            "Stored as a copy to avoid orphaned references when telemetry "
            "is deleted by retention policy. Expected structure: "
            '{"device_id": "uuid", "timestamp": "ISO-8601", "payload": {...}}'
        ),
    )
    status = models.CharField(
        max_length=20, choices=EventStatus.choices, default=EventStatus.NEW
    )

    class Meta:
        db_table = "events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["rule"], name="idx_event_rule"),
            models.Index(fields=["status", "timestamp"], name="idx_event_status_time"),
            models.Index(
                fields=["timestamp", "severity", "status"],
                name="idx_event_time_sev_status",
            ),
            GinIndex(fields=["execution_results"], name="idx_event_exec_results_gin"),
            GinIndex(
                fields=["telemetry_snapshot"], name="idx_event_telemetry_snap_gin"
            ),
        ]

    def __str__(self):
        return f"Event {self.id} - Rule {self.rule_id} - {self.severity}"
