from __future__ import annotations

import csv
import json
from datetime import datetime, time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

from apps.events.models import Event


class Command(BaseCommand):
    help = "Export recent events to CSV for reporting/demo usage."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--since",
            required=True,
            help="ISO-8601 datetime (UTC) or date YYYY-MM-DD.",
        )
        parser.add_argument(
            "--output",
            default="exports/events_export.csv",
            help="Output CSV path (relative to BASE_DIR).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional max number of rows to export.",
        )
        parser.add_argument(
            "--full",
            action="store_true",
            help="Include JSON columns (execution_results, telemetry_snapshot, payload).",
        )

    def handle(self, *args, **opts) -> None:
        since_raw: str = opts["since"]
        output_raw: str = opts["output"]
        limit: int | None = opts["limit"]
        full: bool = opts["full"]

        since_dt = self._parse_since(since_raw)
        output_path = self._resolve_output(output_raw)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        qs = (
            Event.objects.select_related("rule", "rule__device")
            .filter(timestamp__gte=since_dt)
            .order_by("timestamp")
        )
        if limit:
            qs = qs[:limit]

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
        if full:
            fieldnames.extend(
                ["execution_results", "telemetry_snapshot", "payload"]
            )

        count = 0
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for event in qs.iterator():
                snapshot = event.telemetry_snapshot or {}
                payload = snapshot.get("payload")

                row = {
                    "id": event.id,
                    "fired_at": event.timestamp.isoformat(),
                    "rule_name": getattr(event.rule, "name", ""),
                    "rule_id": str(event.rule_id),
                    "device_serial": getattr(
                        getattr(event.rule, "device", None), "serial_number", ""
                    ),
                    "device_id": str(getattr(event.rule, "device_id", "")),
                    "severity": event.severity,
                    "status": event.status,
                    "acknowledged": event.status != Event.EventStatus.NEW,
                    "message": event.message,
                }
                if full:
                    row.update(
                        {
                            "execution_results": json.dumps(event.execution_results),
                            "telemetry_snapshot": json.dumps(snapshot),
                            "payload": json.dumps(payload)
                            if payload is not None
                            else "",
                        }
                    )
                writer.writerow(row)
                count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Exported {count} event(s) to {output_path}")
        )

    def _parse_since(self, raw: str) -> datetime:
        dt = parse_datetime(raw)
        if dt is None:
            date_only = parse_date(raw)
            if date_only:
                dt = datetime.combine(date_only, time.min)

        if dt is None:
            raise CommandError(
                "Invalid --since. Use ISO-8601 datetime or YYYY-MM-DD."
            )

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    def _resolve_output(self, output_raw: str) -> Path:
        output_path = Path(output_raw)
        if not output_path.is_absolute():
            output_path = Path(settings.BASE_DIR) / output_path
        return output_path
