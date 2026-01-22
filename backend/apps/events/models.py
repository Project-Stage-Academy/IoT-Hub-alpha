from django.db import models
from django.contrib.postgres.indexes import GinIndex

from apps.rules.models import Rule


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
    telemetry_id = models.BigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Reference to telemetry (nullable, no FK due to retention policy)",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    severity = models.CharField(max_length=20, choices=EventSeverity.choices)
    message = models.TextField(help_text="Human-readable event description")
    execution_results = models.JSONField(
        help_text=(
            'Schema: [{"type": "notification", "template_id": 5, '
            '"status": "completed", "sent_count": 3, '
            '"completed_at": "2025-01-21T10:00:08Z"}, '
            '{"type": "stop_machine", "machine_id": "M-123", '
            '"status": "failed", "error": "API timeout"}]'
        )
    )
    metadata = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Telemetry snapshot: store a copy of the telemetry data "
            "that triggered this event"
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
            models.Index(fields=["telemetry_id"], name="idx_event_telemetry"),
            models.Index(fields=["status", "timestamp"], name="idx_event_status_time"),
            models.Index(
                fields=["timestamp", "severity", "status"],
                name="idx_event_time_sev_status",
            ),
            GinIndex(fields=["execution_results"], name="idx_event_exec_results_gin"),
        ]

    def __str__(self):
        return f"Event {self.id} - Rule {self.rule_id} - {self.severity}"
