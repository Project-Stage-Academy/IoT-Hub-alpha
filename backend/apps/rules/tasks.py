from celery import shared_task
from django.db.models import Max
from operator import gt, ge, lt, le, eq, ne
from apps.telemetry.models import Telemetry
from .models import Rule, TelemetryCursor
from .services.trigger_engine import trigger_engine

COMPARATORS = {
    "gt": gt,
    "gte": ge,
    "lt": lt,
    "lte": le,
    "eq": eq,
    "ne": ne,
}

@shared_task(bind=True)
def process_telemetry(self, cursor_start: int | None = None, batch_size: int = 1000) -> None:
    cursor = (
        TelemetryCursor.objects
        .aggregate(last_id=Max("last_id"))
        .get("last_id") or 0
    ) if not cursor_start else cursor_start

    telemetry_qs = (
        Telemetry.objects
        .filter(id__gt=cursor)
        .select_related("device")
        .order_by("id")[:batch_size]
    )

    if not telemetry_qs.exists():
        return

    last_processed_id = cursor

    trigger_aggregation = {}
    for telemetry in telemetry_qs.iterator():
        payload = telemetry.payload
        value = payload.get("value")
        device_ssn = telemetry.device.id

        rules = (
            Rule.objects
            .filter(is_enabled=True, device=telemetry.device)
            .only("id", "comparison_operator", "threshold")
        )

        for rule in rules:
            comparator = COMPARATORS.get(rule.comparison_operator)
            if not comparator:
                continue

            if comparator(value, rule.threshold):
                if rule.id in trigger_aggregation:
                    trigger_aggregation[rule.id]['values'].append(value)
                    trigger_aggregation[rule.id]['end'] = telemetry.timestamp
                else:
                    trigger_aggregation[rule.id] = {
                        "device": device_ssn,
                        "rule": rule,
                        "values": [value],
                        "start": telemetry.timestamp,
                    }
        last_processed_id = telemetry.id
    trigger_engine(trigger_aggregation)

    TelemetryCursor.objects.update_or_create(
        defaults={"last_id": last_processed_id}
    )
