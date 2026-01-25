from django.contrib import admin
from django.contrib import messages

from .models import Rule


@admin.action(description="Enable selected rules")
def enable_rules(modeladmin, request, queryset):
    updated = queryset.update(is_enabled=True)
    modeladmin.message_user(
        request,
        f"{updated} rule(s) enabled.",
        messages.SUCCESS,
    )


@admin.action(description="Disable selected rules")
def disable_rules(modeladmin, request, queryset):
    updated = queryset.update(is_enabled=False)
    modeladmin.message_user(
        request,
        f"{updated} rule(s) disabled.",
        messages.SUCCESS,
    )


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "device",
        "comparison_operator",
        "threshold",
        "is_enabled",
        "last_triggered_at",
        "created_at",
    ]
    list_filter = ["is_enabled", "comparison_operator", "device", "created_at"]
    search_fields = ["name", "description", "device__name", "device__serial_number"]
    readonly_fields = ["id", "created_at", "updated_at", "last_triggered_at"]
    date_hierarchy = "created_at"
    actions = [enable_rules, disable_rules]
