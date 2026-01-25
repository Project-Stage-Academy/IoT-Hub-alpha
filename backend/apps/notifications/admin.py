from django.contrib import admin
from django.contrib import messages

from .models import NotificationTemplate, NotificationDelivery


@admin.action(description="Activate selected templates")
def activate_templates(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(
        request,
        f"{updated} template(s) activated.",
        messages.SUCCESS,
    )


@admin.action(description="Deactivate selected templates")
def deactivate_templates(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    modeladmin.message_user(
        request,
        f"{updated} template(s) deactivated.",
        messages.SUCCESS,
    )


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "priority",
        "is_active",
        "retry_count",
        "retry_delay_minutes",
        "created_at",
    ]
    list_filter = ["is_active", "priority", "created_at"]
    search_fields = ["name", "message_template"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"
    actions = [activate_templates, deactivate_templates]


@admin.action(description="Mark selected deliveries as pending")
def mark_pending(modeladmin, request, queryset):
    updated = queryset.exclude(status="pending").update(status="pending")
    modeladmin.message_user(
        request,
        f"{updated} delivery(ies) marked as pending.",
        messages.SUCCESS,
    )


@admin.action(description="Reset attempt count for selected deliveries")
def reset_attempts(modeladmin, request, queryset):
    updated = queryset.update(attempt_count=0)
    modeladmin.message_user(
        request,
        f"{updated} delivery(ies) attempt count reset.",
        messages.SUCCESS,
    )


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "event",
        "template",
        "notification_type",
        "recipient_address",
        "status",
        "attempt_count",
        "sent_at",
        "created_at",
    ]
    list_filter = ["status", "notification_type", "template", "created_at", "sent_at"]
    search_fields = [
        "recipient_address",
        "recipient_name",
        "rendered_message",
        "event__message",
    ]
    readonly_fields = ["id", "created_at", "sent_at", "last_attempt_at"]
    date_hierarchy = "created_at"
    actions = [mark_pending, reset_attempts]
