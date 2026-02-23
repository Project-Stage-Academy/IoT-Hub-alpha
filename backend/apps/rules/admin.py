from django.contrib import admin
from django.contrib import messages
from .models import Rule


@admin.action(description="Enable selected rules")
def enable_rules(modeladmin, request, queryset):
    """
    Django admin action to enable selected rules.

    Bulk-updates is_enabled=True for selected Rule instances and displays
    success message with count. Called from Rule admin change list when user
    selects rules and chooses "Enable selected rules" action.

    Args:
        modeladmin: RuleAdmin instance
        request: HTTP request object
        queryset: QuerySet of Rule instances to enable
    """
    updated = queryset.update(is_enabled=True)
    modeladmin.message_user(
        request,
        f"{updated} rule(s) enabled.",
        messages.SUCCESS,
    )


@admin.action(description="Disable selected rules")
def disable_rules(modeladmin, request, queryset):
    """
    Django admin action to disable selected rules.

    Bulk-updates is_enabled=False for selected Rule instances and displays
    success message with count. Called from Rule admin change list when user
    selects rules and chooses "Disable selected rules" action.

    Args:
        modeladmin: RuleAdmin instance
        request: HTTP request object
        queryset: QuerySet of Rule instances to disable
    """
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
        "condition",
        "is_enabled",
        "last_triggered_at",
        "created_at",
    ]
    list_filter = ["is_enabled", "device", "created_at"]
    search_fields = ["name", "description", "device__name", "device__serial_number"]
    readonly_fields = ["id", "created_at", "updated_at", "last_triggered_at"]
    date_hierarchy = "created_at"
    actions = [enable_rules, disable_rules]
