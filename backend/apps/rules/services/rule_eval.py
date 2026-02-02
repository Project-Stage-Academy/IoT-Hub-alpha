from dataclasses import dataclass, field
import os
from uuid import UUID
from datetime import datetime, timedelta
from typing import Any
from django.utils import timezone
from .data_structure import Condition, AggregateStructure
from apps.telemetry.models import Telemetry
from operator import gt, ge, lt, le, eq, ne
from django.db.models import Min, Max
from django.db.models import FloatField
from django.db.models.functions import Cast

COMPARATORS = {
    "gt": gt,
    "gte": ge,
    "lt": lt,
    "lte": le,
    "eq": eq,
    "ne": ne,
}

CELERY_PROCESS_TIMER = os.getenv("CELERY_RUN_PROCESS_TELEMETRY_TIMER_MINUTES", 5)

@dataclass(frozen=True)
class TelemetryPoint:
    ts: datetime
    value: float
    
@dataclass()
class EvalResults:
    trigger: bool
    values: list[float] = field(default_factory=list)
    start: datetime | None = None
    end: datetime | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "values": self.values,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
        }
    

def _eval_condition(operator: str, threshold: float, telemetry_chunk: list[TelemetryPoint], aggregate_trigger: EvalResults) -> EvalResults:
    trigger_values: list[float] = []
    start = None
    end = None
    for telemetry in telemetry_chunk:
        try:
            trigger = COMPARATORS[operator](telemetry.value, threshold)
        except KeyError:
            raise ValueError(f"Unknown operator: {operator}")
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
    
def _window_eval(operator, threshold, telemetry_chunks, window_seconds, occurrences, device_id, aggregate_trigger: EvalResults) -> EvalResults:
    cmp = COMPARATORS[operator]
    now = timezone.now()
    if int(CELERY_PROCESS_TIMER)*60 < window_seconds:
        since = now - timedelta(seconds=window_seconds)
        qs = (
            Telemetry.objects
            .filter(timestamp__gte=since, device_id=device_id)
            .annotate(value=Cast("payload__value", FloatField()))
            )
        qs = qs.filter(**{f"value__{operator}": threshold})
        agg = qs.aggregate(min_ts=Min("timestamp"), max_ts=Max("timestamp"))
        values = list(qs.values_list("payload__value", flat=True))
        aggregate_trigger.trigger = True if qs.count() >= occurrences else False
        aggregate_trigger.start = agg.get('min_ts', 0)
        aggregate_trigger.end = agg.get('max_ts', 0)
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
        
            aggregate_trigger.trigger = True if matched else False
            aggregate_trigger.start = matched[0].ts if matched else None
            aggregate_trigger.end = matched[-1].ts if matched else None
            aggregate_trigger.values = [p.value for p in matched]
        
        
    return aggregate_trigger
    
def eval_rule(condition: Condition,
              telemetry_chunks: list[TelemetryPoint],
              aggregate_trigger: EvalResults,
              device_id: UUID,
              ) -> EvalResults:
    
    type = condition.type
    
    if type == "leaf":
        if condition.window_seconds and condition.occurrences:
            aggregate_trigger = _window_eval(condition.operator,
                                    condition.threshold,
                                    telemetry_chunks,
                                    condition.window_seconds,
                                    condition.occurrences,
                                    device_id,
                                    aggregate_trigger)
            return aggregate_trigger
        
        else:
            if condition.operator and condition.threshold:
                aggregate_trigger = _eval_condition(condition.operator,
                                            condition.threshold,
                                            telemetry_chunks,
                                            aggregate_trigger)
                return aggregate_trigger
                
    if type == "and":
        if not condition.conditions:
            raise KeyError(f"Malformed condition: {condition}")
        child_results = [
            eval_rule(c, telemetry_chunks, aggregate_trigger, device_id)
            for c in condition.conditions
        ]
        aggregate_trigger.trigger = all(r.trigger for r in child_results)
        aggregate_trigger.values = [v for r in child_results for v in r.values]
        return aggregate_trigger

    if type == "or":
        if not condition.conditions:
            raise KeyError(f"Malformed condition: {condition}")
        child_results = [
            eval_rule(c, telemetry_chunks, aggregate_trigger, device_id)
            for c in condition.conditions
        ]
        aggregate_trigger.trigger = any(r.trigger for r in child_results)
        aggregate_trigger.values = [v for r in child_results if r.trigger for v in r.values]
        return aggregate_trigger

    return aggregate_trigger