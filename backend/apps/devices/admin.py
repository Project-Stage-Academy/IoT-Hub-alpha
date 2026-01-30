from django.contrib import admin
from django.contrib import messages
from django.conf import settings

from .models import Device, DeviceType
from apps.telemetry.models import Telemetry


DEVICE_TELEMETRY_INLINE_LIMIT = getattr(settings, "DEVICE_TELEMETRY_INLINE_LIMIT", 1)


class RecentTelemetryInline(admin.TabularInline):
    model = Telemetry
    fk_name = "device"
    extra = 0
    max_num = 0
    can_delete = False
    verbose_name = "Recent Telemetry"
    verbose_name_plural = f"Recent Telemetry (last {DEVICE_TELEMETRY_INLINE_LIMIT})"
    readonly_fields = ["id", "timestamp", "payload_short"]
    fields = ["id", "timestamp", "payload_short"]
    ordering = ["-timestamp"]

    def get_formset(self, request, obj=None, **kwargs):
        self.parent_object = obj
        return super().get_formset(request, obj, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if hasattr(self, "parent_object") and self.parent_object:
            recent_ids = list(
                Telemetry.objects.filter(device=self.parent_object)
                .order_by("-timestamp")
                .values_list("id", flat=True)[:DEVICE_TELEMETRY_INLINE_LIMIT]
            )
            return qs.filter(id__in=recent_ids).order_by("-timestamp")
        return qs.none()

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Payload")
    def payload_short(self, obj):
        import json

        if obj.payload:
            text = json.dumps(obj.payload)
            if len(text) > 80:
                return f"{text[:80]}..."
            return text
        return "-"


@admin.action(description="Activate selected devices")
def activate_devices(modeladmin, request, queryset):
    updated = queryset.update(status="active")
    modeladmin.message_user(
        request,
        f"{updated} device(s) activated.",
        messages.SUCCESS,
    )


@admin.action(description="Deactivate selected devices")
def deactivate_devices(modeladmin, request, queryset):
    updated = queryset.update(status="inactive")
    modeladmin.message_user(
        request,
        f"{updated} device(s) deactivated.",
        messages.SUCCESS,
    )


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "serial_number",
        "device_type",
        "status",
        "location",
        "last_seen",
        "created_at",
    ]
    list_filter = ["status", "device_type", "created_at", "last_seen"]
    search_fields = ["name", "serial_number", "location"]
    readonly_fields = ["id", "created_at", "updated_at", "last_seen"]
    date_hierarchy = "created_at"
    actions = [activate_devices, deactivate_devices]
    inlines = [RecentTelemetryInline]
