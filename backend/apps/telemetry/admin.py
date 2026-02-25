import csv
import json

from django.contrib import admin
from django.http import HttpResponse

from .models import Telemetry, TelemetrySchema


@admin.action(description="Export selected telemetry to CSV")
def export_to_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="telemetry_export.csv"'

    writer = csv.writer(response)
    writer.writerow(["ID", "Device", "Device Serial", "Timestamp", "Payload"])

    for telemetry in queryset.select_related("device"):
        writer.writerow(
            [
                telemetry.id,
                telemetry.device.name,
                telemetry.device.serial_number,
                telemetry.timestamp.isoformat(),
                json.dumps(telemetry.payload),
            ]
        )

    return response


@admin.register(Telemetry)
class TelemetryAdmin(admin.ModelAdmin):
    list_display = ["id", "device", "timestamp"]
    list_filter = ["device", "timestamp"]
    list_select_related = ["device"]
    search_fields = ["device__name", "device__serial_number"]
    readonly_fields = ["id", "timestamp", "payload"]
    date_hierarchy = "timestamp"
    list_per_page = 50
    actions = [export_to_csv]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("device")


@admin.register(TelemetrySchema)
class TelemetrySchemaAdmin(admin.ModelAdmin):
    list_display = ["version", "schema_summary", "rules_summary", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["version"]
    list_per_page = 50

    @admin.display(description="Validation Schema")
    def schema_summary(self, obj):
        """Returns a summary for the Validation Schema column."""
        schema = obj.validation_schema
        if not schema or not isinstance(schema, dict):
            return "Empty"

        keys_count = len(schema.keys())
        return f"Configured ({keys_count} keys)"

    @admin.display(description="Transformation Rules")
    def rules_summary(self, obj):
        """
        Returns a summary of active transformation rules
        for the Transformation Rules column.
        """
        rules = obj.transformation_rules
        if not rules or not isinstance(rules, dict):
            return "No rules"

        active_rules = list(rules.keys())
        return f"Active: {', '.join(active_rules)}"
