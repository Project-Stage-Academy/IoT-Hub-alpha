import os
import logging
from celery import shared_task
from uuid import UUID
from django.db.models import Max
from collections import defaultdict
from datetime import datetime
from apps.telemetry.models import Telemetry
from .models import Rule, TelemetryCursor
from .services.rule_eval import eval_rule, TelemetryPoint
from .services.trigger_engine import trigger_engine
from .services.data_structure import Condition, EvalResults

BATCH_SIZE = os.getenv("CELERY_RULE_BATCH_SIZE", 1000)

logger = logging.getLogger("apps.rules")


@shared_task(bind=True, name="apps.rules.tasks.process_telemetry")
def process_telemetry(
    self,
    cursor_start: int | None = None,
    batch_size: int = int(BATCH_SIZE),
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

    # root = logging.getLogger()

    # logger.info("logger_handlers", extra=
    # {"event":
    # {"handlers": [type(h).__name__ for h in logger.handlers]}})
    # root.info("root_handlers", extra=
    # {"event": {"handlers": [type(h).__name__ for h in root.handlers]}})

    cursor = (
        (TelemetryCursor.objects.aggregate(last_id=Max("last_id")).get("last_id") or 0)
        if cursor_start is None
        else cursor_start
    )

    last_id = cursor

    telemetry_qs = (
        Telemetry.objects.filter(id__gt=cursor)
        .select_related("device")
        .order_by("id")[:batch_size]
    )

    if not telemetry_qs.exists():
        logger.info(
            "logger_handlers", extra={"event": {"msg": "No telemetry detected"}}
        )
        return

    rules = Rule.objects.filter(is_enabled=True).only(
        "id", "condition", "action_config", "device_id"
    )

    rules_by_device: dict[UUID, list[Rule]] = defaultdict(list)
    telemetry_by_device: dict[UUID, list[TelemetryPoint]] = defaultdict(list)

    for rule in rules:
        rules_by_device[rule.device_id].append(rule)  # type: ignore[attr-defined]

    for telemetry in telemetry_qs.iterator():
        telemetry_by_device[telemetry.device_id].append(  # type: ignore[attr-defined]
            TelemetryPoint(ts=telemetry.timestamp, value=telemetry.payload.get("value"))
        )
        last_id += 1

    rule_aggregation: dict[UUID, EvalResults] = defaultdict()

    for device, rules in rules_by_device.items():
        for rule in rules:
            condition = Condition.model_validate(rule.condition)
            result = eval_rule(
                condition,
                telemetry_by_device[rule.device_id],  # type: ignore[attr-defined]
                EvalResults(),
                rule.device_id,
            )  # type: ignore[attr-defined]
            if result.trigger:
                rule_aggregation[rule.id] = result
                logger.info(
                    "rule_fired",
                    extra={
                        "event": {
                            "rule": rule_aggregation[rule.id],
                            "rule_type": condition.type,
                            "device_id": rule.device_id,  # type: ignore[attr-defined]
                            "telemetry_id": cursor,
                            "evaluated_at": datetime.now().isoformat(),
                            "reason": f"{', '.join(str(result.values))}"
                            f" {condition.type} {condition.threshold}",
                        }
                    },
                )

    trigger_engine(rule_aggregation)

    if record_cursor:
        TelemetryCursor.objects.update_or_create(defaults={"last_id": last_id})
