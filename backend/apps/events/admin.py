from django.contrib import admin
from django.contrib import messages

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
    list_display = ["id", "rule", "severity", "status", "timestamp"]
    list_filter = ["severity", "status", "timestamp", "rule"]
    search_fields = ["message", "rule__name"]
    readonly_fields = ["id", "timestamp", "execution_results", "telemetry_snapshot"]
    date_hierarchy = "timestamp"
    actions = [acknowledge_events, resolve_events, mark_events_new]
