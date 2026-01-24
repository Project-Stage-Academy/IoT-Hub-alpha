from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

from apps.events.models import Event


class NotificationPriority(models.IntegerChoices):
    LOW = 1, "Low Priority"
    MEDIUM = 2, "Medium Priority"
    HIGH = 3, "High Priority"
    CRITICAL = 4, "Critical Priority"


def validate_recipients(value):
    """Validates recipients JSON structure."""
    if not isinstance(value, list):
        raise ValidationError("recipients must be a list of recipient items")

    if len(value) == 0:
        raise ValidationError("recipients list cannot be empty")

    for item in value:
        if not isinstance(item, dict):
            raise ValidationError("Each recipient must be a dictionary")

        if "type" not in item:
            raise ValidationError("Each recipient must have a 'type' field")

        recipient_type = item.get("type")

        # Type-specific validation
        if recipient_type == "email":
            if "address" not in item:
                raise ValidationError("Email recipient must have an 'address' field")
        elif recipient_type == "sms":
            if "phone" not in item:
                raise ValidationError("SMS recipient must have a 'phone' field")
        elif recipient_type == "webhook":
            if "url" not in item:
                raise ValidationError("Webhook recipient must have a 'url' field")
        else:
            raise ValidationError(f"Unknown recipient type: {recipient_type}")


class NotificationTemplate(models.Model):

    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    message_template = models.TextField(
        help_text='Template with placeholders: "Alert {severity}: {message}"'
    )
    recipients = models.JSONField(
        validators=[validate_recipients],
        help_text=(
            'Schema: [{"type": "email", "address": "admin@company.com"}, '
            '{"type": "sms", "phone": "+380501234567"}]'
        ),
    )
    priority = models.IntegerField(
        choices=NotificationPriority.choices,
        default=NotificationPriority.MEDIUM,
        validators=[MinValueValidator(1)],
    )
    retry_count = models.IntegerField(default=3, validators=[MinValueValidator(1)])
    retry_delay_minutes = models.IntegerField(
        default=5, validators=[MinValueValidator(1)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_templates"
        ordering = ["priority", "name"]
        indexes = [
            models.Index(fields=["name"], name="idx_notif_templ_name"),
            models.Index(fields=["is_active"], name="idx_notif_templ_active"),
            models.Index(fields=["priority"], name="idx_notif_templ_priority"),
            GinIndex(fields=["recipients"], name="idx_notif_templ_recip_gin"),
        ]

    def __str__(self):
        return f"{self.name} (Priority: {self.priority})"


class NotificationDelivery(models.Model):

    class NotificationType(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WEBHOOK = "webhook", "Webhook"

    class NotificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.BigAutoField(primary_key=True)
    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="notification_deliveries"
    )
    template = models.ForeignKey(
        NotificationTemplate, on_delete=models.PROTECT, related_name="deliveries"
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
    )
    recipient_address = models.TextField(
        help_text=("Email address, phone number, or webhook URL")
    )
    recipient_name = models.CharField(max_length=255, null=True, blank=True)
    rendered_message = models.TextField(
        help_text=(
            "Final message after template rendering with actual values "
            "(e.g., device name, metric value)"
        )
    )
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
    )

    attempt_count = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(
        blank=True, null=True, help_text="Error details if status = failed"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_deliveries"
        ordering = ["status", "-created_at"]
        indexes = [
            models.Index(fields=["event"], name="idx_notif_deliv_event"),
            models.Index(
                fields=["status", "created_at"],
                name="idx_notif_deliv_queue",
            ),
            models.Index(
                fields=["status", "attempt_count", "last_attempt_at"],
                name="idx_notif_deliv_retry",
            ),
        ]
        verbose_name_plural = "Notification deliveries"

    def __str__(self):
        return (
            f"Delivery {self.id} - {self.notification_type} to "
            f"{self.recipient_address} ({self.status})"
        )
