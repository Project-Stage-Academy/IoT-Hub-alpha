import csv
import json

from django.contrib import admin
from django.http import HttpResponse

from .models import Telemetry


@admin.action(description="Export selected telemetry to CSV")
def export_to_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="telemetry_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Device', 'Device Serial', 'Timestamp', 'Payload'])

    for telemetry in queryset.select_related('device'):
        writer.writerow([
            telemetry.id,
            telemetry.device.name,
            telemetry.device.serial_number,
            telemetry.timestamp.isoformat(),
            json.dumps(telemetry.payload),
        ])

    return response


@admin.register(Telemetry)
class TelemetryAdmin(admin.ModelAdmin):
    list_display = ['id', 'device', 'timestamp']
    list_filter = ['device', 'timestamp']
    search_fields = ['device__name', 'device__serial_number']
    readonly_fields = ['id', 'timestamp', 'payload']
    date_hierarchy = 'timestamp'
    actions = [export_to_csv]
