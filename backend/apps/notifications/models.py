from django.db import models
from django.contrib.postgres.indexes import GinIndex

from apps.events.models import Event


class NotificationTemplate(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    message_template = models.TextField(
        help_text='Template with placeholders: "Alert {severity}: {message}"'
    )
    recipients = models.JSONField(
        help_text='Schema: [{"type": "email", "address": "admin@company.com"}, {"type": "sms", "phone": "+380501234567"}]'
    )
    priority = models.IntegerField(default=1)
    retry_count = models.IntegerField(default=3)
    retry_delay_minutes = models.IntegerField(default=5)
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
        Event,
        on_delete=models.CASCADE,
        related_name="notification_deliveries"
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.PROTECT,
        related_name="deliveries"
    )
    recipient_type = models.CharField(max_length=20, choices=NotificationType.choices)
    recipient_address = models.TextField(help_text="Email address, phone number, or webhook URL")
    recipient_name = models.CharField(max_length=255, null=True, blank=True)
    rendered_message = models.TextField(help_text="Actual message sent (snapshot)")
    status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING
    )
    priority = models.IntegerField(default=1)
    attempt_count = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error details if status = failed"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "notification_deliveries"
        ordering = ["status", "priority", "-created_at"]
        indexes = [
            models.Index(fields=["event"], name="idx_notif_deliv_event"),
            models.Index(fields=["status", "priority", "created_at"], name="idx_notif_deliv_queue"),
            models.Index(fields=["status", "attempt_count", "last_attempt_at"], name="idx_notif_deliv_retry"),
        ]
        verbose_name_plural = "Notification deliveries"
    
    def __str__(self):
        return f"Delivery {self.id} - {self.recipient_type} to {self.recipient_address} ({self.status})"

