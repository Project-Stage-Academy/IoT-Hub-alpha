import os
import logging
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime, timedelta
from operator import gt, ge, lt, le, eq, ne
from django.utils import timezone
from django.db.models import Min, Max
from django.db.models import FloatField
from django.db.models.functions import Cast
from .data_structure import Condition, EvalResults
from apps.telemetry.models import Telemetry

COMPARATORS = {
    "gt": gt,
    "gte": ge,
    "lt": lt,
    "lte": le,
    "eq": eq,
    "ne": ne,
}

CELERY_PROCESS_TIMER = os.getenv("CELERY_RUN_PROCESS_TELEMETRY_TIMER_MINUTES", 5)
logger = logging.getLogger("apps.rules")


@dataclass(frozen=True)
class TelemetryPoint:
    ts: datetime
    value: float


def _eval_condition(
    operator: str,
    threshold: float,
    telemetry_chunk: list[TelemetryPoint],
    aggregate_trigger: EvalResults,
) -> EvalResults:
    trigger_values: list[float] = []
    start = None
    end = None
    for telemetry in telemetry_chunk:
        try:
            trigger = COMPARATORS[operator](telemetry.value, threshold)
        except KeyError:
            logger.warning(
                "Unknown operator",
                extra={
                    "event": {
                        "error": f"Unknown operator detected: {COMPARATORS[operator]}"
                    }
                },
            )
            continue
        if trigger:
            trigger_values.append(telemetry.value)
            if not start:
                start = telemetry.ts
            end = telemetry.ts

            aggregate_trigger.trigger = True if trigger_values else False
            aggregate_trigger.start = start
            aggregate_trigger.end = end
            aggregate_trigger.values = trigger_values

    return aggregate_trigger


def _window_eval(
    operator,
    threshold,
    telemetry_chunks,
    window_seconds,
    occurrences,
    device_id,
    aggregate_trigger: EvalResults,
) -> EvalResults:
    cmp = COMPARATORS[operator]
    now = timezone.now()
    if int(CELERY_PROCESS_TIMER) * 60 < window_seconds:
        since = now - timedelta(seconds=window_seconds)
        qs = Telemetry.objects.filter(
            timestamp__gte=since, device_id=device_id
        ).annotate(value=Cast("payload__value", FloatField()))
        qs = qs.filter(**{f"value__{operator}": threshold})
        agg = qs.aggregate(min_ts=Min("timestamp"), max_ts=Max("timestamp"))
        values = list(qs.values_list("payload__value", flat=True))
        aggregate_trigger.trigger = True if qs.count() >= occurrences else False
        aggregate_trigger.start = agg.get("min_ts", 0)
        aggregate_trigger.end = agg.get("max_ts", 0)
        aggregate_trigger.values = values

    else:
        pts = sorted(telemetry_chunks, key=lambda p: p.ts)
        window = timedelta(seconds=window_seconds)

        left = 0
        match_count = 0
        matched = []

        for right in range(len(pts)):
            if cmp(pts[right].value, threshold):
                match_count += 1

            while pts[right].ts - pts[left].ts > window:
                if cmp(pts[left].value, threshold):
                    match_count -= 1
                left += 1

            if match_count >= occurrences:
                window_points = pts[left : right + 1]
                matched = [p for p in window_points if cmp(p.value, threshold)]
                break

        if matched:
            aggregate_trigger.trigger = True
            aggregate_trigger.start = matched[0].ts
            aggregate_trigger.end = matched[-1].ts
            aggregate_trigger.values = [p.value for p in matched]
        else:
            aggregate_trigger.trigger = False
            aggregate_trigger.start = None
            aggregate_trigger.end = None
            aggregate_trigger.values = []

    return aggregate_trigger


def eval_rule(
    condition: Condition,
    telemetry_chunks: list[TelemetryPoint],
    aggregate_trigger: EvalResults,
    device_id: UUID,
) -> EvalResults:

    type = condition.type

    if type == "leaf":
        if condition.window_seconds and condition.occurrences:
            aggregate_trigger = _window_eval(
                condition.operator,
                condition.threshold,
                telemetry_chunks,
                condition.window_seconds,
                condition.occurrences,
                device_id,
                aggregate_trigger,
            )
            return aggregate_trigger

        else:
            if condition.operator and condition.threshold:
                aggregate_trigger = _eval_condition(
                    condition.operator,
                    condition.threshold,
                    telemetry_chunks,
                    aggregate_trigger,
                )
                return aggregate_trigger

    if type == "and":
        if not condition.conditions:
            logger.warning(
                "Malformed config!",
                extra={
                    "event": {"error": "Malformed config detected - missing conditions"}
                },
            )
        child_results = [
            eval_rule(c, telemetry_chunks, EvalResults(), device_id)
            for c in condition.conditions
        ]
        aggregate_trigger.trigger = all(r.trigger for r in child_results)
        if aggregate_trigger.trigger:
            aggregate_trigger.values = child_results[0].values
        return aggregate_trigger

    if type == "or":
        if not condition.conditions:
            logger.warning(
                "Malformed config!",
                extra={
                    "event": {"error": "Malformed config detected - missing conditions"}
                },
            )
        child_results = [
            eval_rule(c, telemetry_chunks, EvalResults(), device_id)
            for c in condition.conditions
        ]
        aggregate_trigger.trigger = any(r.trigger for r in child_results)
        for r in child_results:
            if r.trigger:
                aggregate_trigger.values = r.values
                break
        return aggregate_trigger

    return aggregate_trigger
