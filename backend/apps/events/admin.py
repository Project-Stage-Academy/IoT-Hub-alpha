from django.contrib import admin
from django.contrib import messages
from django.urls import reverse
from django.utils.html import format_html

from .models import Event


@admin.action(description="Acknowledge selected events")
def acknowledge_events(modeladmin, request, queryset):
    updated = queryset.filter(status="new").update(status="acknowledged")
    modeladmin.message_user(
        request,
        f"{updated} event(s) acknowledged.",
        messages.SUCCESS,
    )


@admin.action(description="Resolve selected events")
def resolve_events(modeladmin, request, queryset):
    updated = queryset.exclude(status="resolved").update(status="resolved")
    modeladmin.message_user(
        request,
        f"{updated} event(s) resolved.",
        messages.SUCCESS,
    )


@admin.action(description="Mark selected events as new")
def mark_events_new(modeladmin, request, queryset):
    updated = queryset.exclude(status="new").update(status="new")
    modeladmin.message_user(
        request,
        f"{updated} event(s) marked as new.",
        messages.SUCCESS,
    )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "rule_link",
        "device_link",
        "telemetry_link",
        "severity",
        "status",
        "timestamp",
    ]
    list_filter = ["severity", "status", "timestamp", "rule", "rule__device"]
    search_fields = [
        "message",
        "rule__name",
        "rule__device__name",
        "rule__device__serial_number",
    ]
    readonly_fields = [
        "id",
        "timestamp",
        "rule_link",
        "device_link",
        "telemetry_link",
        "execution_results",
        "telemetry_snapshot",
    ]
    date_hierarchy = "timestamp"
    actions = [acknowledge_events, resolve_events, mark_events_new]
    list_select_related = ["rule", "rule__device"]

    @admin.display(description="Rule", ordering="rule__name")
    def rule_link(self, obj: Event):
        url = reverse("admin:rules_rule_change", args=[obj.rule_id])
        return format_html('<a href="{}">{}</a>', url, obj.rule.name)

    @admin.display(description="Device", ordering="rule__device__name")
    def device_link(self, obj: Event):
        device = obj.rule.device
        url = reverse("admin:devices_device_change", args=[device.id])
        return format_html('<a href="{}">{}</a>', url, device.name)

    @admin.display(description="Telemetry")
    def telemetry_link(self, obj: Event):
        snapshot = obj.telemetry_snapshot or {}
        device_id = snapshot.get("device_id") or str(obj.rule.device_id)
        if not device_id:
            return "-"
        url = reverse("admin:telemetry_telemetry_changelist")
        return format_html(
            '<a href="{}?device__id__exact={}">Telemetry</a>', url, device_id
        )
