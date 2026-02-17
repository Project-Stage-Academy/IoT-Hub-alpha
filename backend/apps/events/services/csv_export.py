from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from apps.events.models import Event


@dataclass
class EventCsvExportService:
    since_dt: datetime
    until_dt: datetime | None = None
    limit: int | None = None
    full: bool = False

    def export(self, *, output_path: Path) -> int:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = self._fieldnames()

        count = 0
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for event in self._queryset().iterator():
                writer.writerow(self._build_row(event))
                count += 1
        return count

    def _queryset(self):
        queryset = Event.objects.select_related("rule", "rule__device").filter(
            timestamp__gte=self.since_dt
        )
        if self.until_dt is not None:
            queryset = queryset.filter(timestamp__lte=self.until_dt)
        queryset = queryset.order_by("timestamp")

        if self.limit is not None:
            queryset = queryset[: self.limit]
        return queryset

    def _fieldnames(self) -> list[str]:
        fieldnames = [
            "id",
            "fired_at",
            "rule_name",
            "rule_id",
            "device_serial",
            "device_id",
            "severity",
            "status",
            "acknowledged",
            "message",
        ]
        if self.full:
            fieldnames.extend(["execution_results", "telemetry_snapshot", "payload"])
        return fieldnames

    def _build_row(self, event: Event) -> dict[str, Any]:
        snapshot = event.telemetry_snapshot or {}
        payload = snapshot.get("payload")
        created_at = event.timestamp.isoformat()
        fired_at = snapshot.get("timestamp")
        if not isinstance(fired_at, str) or not fired_at:
            fired_at = created_at

        row: dict[str, Any] = {
            "id": event.id,
            "fired_at": fired_at,
            "rule_name": getattr(event.rule, "name", ""),
            "rule_id": str(event.rule_id),
            "device_serial": getattr(
                getattr(event.rule, "device", None), "serial_number", ""
            ),
            "device_id": str(getattr(event.rule, "device_id", "")),
            "severity": event.severity,
            "status": event.status,
            "acknowledged": event.acknowledged,
            "message": event.message,
        }
        if self.full:
            row.update(
                {
                    "execution_results": json.dumps(event.execution_results),
                    "telemetry_snapshot": json.dumps(snapshot),
                    "payload": json.dumps(payload) if payload is not None else "",
                }
            )
        return row
