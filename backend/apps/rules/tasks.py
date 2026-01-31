from celery import shared_task
from uuid import UUID
from django.db.models import Max
from operator import gt, ge, lt, le, eq, ne
from collections import defaultdict
from apps.telemetry.models import Telemetry
from .models import Rule, TelemetryCursor
from .services.trigger_engine import trigger_engine
from .services.data_structure import AggregateStructure

COMPARATORS = {
    "gt": gt,
    "gte": ge,
    "lt": lt,
    "lte": le,
    "eq": eq,
    "ne": ne,
}


@shared_task(bind=True)
def process_telemetry(
    self,
    cursor_start: int | None = None,
    batch_size: int = 1000,
    record_cursor: bool = True,
) -> None:
    """
    Get telemetry from DB and compare to set rules, manage cursor

    :param self: Description
    :param cursor_start: Description
    :type cursor_start: int | None
    :param batch_size: Description
    :type batch_size: int
    :param record_cursor: Description
    :type record_cursor: bool
    """
    cursor = (
        (TelemetryCursor.objects.aggregate(last_id=Max("last_id")).get("last_id") or 0)
        if cursor_start is None
        else cursor_start
    )

    telemetry_qs = (
        Telemetry.objects.filter(id__gt=cursor)
        .select_related("device")
        .order_by("id")[:batch_size]
    )

    if not telemetry_qs.exists():
        return

    rules = Rule.objects.filter(is_enabled=True).only(
        "id", "comparison_operator", "threshold", "device_id"
    )

    rules_by_device: dict[UUID, list[Rule]] = defaultdict(list)
    for rule in rules:
        rules_by_device[rule.device_id].append(rule)

    trigger_aggregation: dict[UUID, AggregateStructure] = {}
    for telemetry in telemetry_qs.iterator():
        payload = telemetry.payload
        value: float = payload.get("value")

        if value is None:
            continue

        device_rules = rules_by_device.get(telemetry.device_id, [])

        for rule in device_rules:
            comparator = COMPARATORS.get(rule.comparison_operator)
            if not comparator:
                continue

            if comparator(value, rule.threshold):
                if rule.id in trigger_aggregation:
                    agg = trigger_aggregation[rule.id]
                    agg.values.append(value)
                    agg.end = telemetry.timestamp
                else:
                    trigger_aggregation[rule.id] = AggregateStructure(
                        rule_id=rule.id,
                        values=[value],
                        start=telemetry.timestamp,
                        end=telemetry.timestamp,
                    )
        cursor = telemetry.id
    trigger_engine(trigger_aggregation)

    if record_cursor:
        TelemetryCursor.objects.update_or_create(defaults={"last_id": cursor})
