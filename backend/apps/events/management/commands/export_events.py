from __future__ import annotations

from datetime import datetime, time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

from apps.events.services.csv_export import EventCsvExportService


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
        parser.add_argument(
            "--until",
            required=False,
            help=(
                "Optional upper bound (inclusive), ISO-8601 datetime "
                "or date YYYY-MM-DD."
            ),
        )

    def handle(self, *args, **opts) -> None:
        since_raw: str = opts["since"]
        until_raw: str | None = opts.get("until")
        output_raw: str = opts["output"]
        limit: int | None = opts["limit"]
        full: bool = opts["full"]

        since_dt = self._parse_boundary(
            since_raw, arg_name="since", use_end_of_day=False
        )
        until_dt: datetime | None = None
        if until_raw:
            until_dt = self._parse_boundary(
                until_raw, arg_name="until", use_end_of_day=True
            )
            if until_dt < since_dt:
                raise CommandError("--until must be greater than or equal to --since.")

        if limit is not None and limit < 1:
            raise CommandError("--limit must be >= 1.")

        output_path = self._resolve_output(output_raw)
        exporter = EventCsvExportService(
            since_dt=since_dt,
            until_dt=until_dt,
            limit=limit,
            full=full,
        )
        count = exporter.export(output_path=output_path)

        self.stdout.write(
            self.style.SUCCESS(f"Exported {count} event(s) to {output_path}")
        )

    def _parse_boundary(
        self,
        raw: str,
        *,
        arg_name: str,
        use_end_of_day: bool,
    ) -> datetime:
        dt = parse_datetime(raw)
        if dt is None:
            date_only = parse_date(raw)
            if date_only:
                default_time = time.max if use_end_of_day else time.min
                dt = datetime.combine(date_only, default_time)

        if dt is None:
            raise CommandError(
                f"Invalid --{arg_name}. Use ISO-8601 datetime or YYYY-MM-DD."
            )

        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    def _resolve_output(self, output_raw: str) -> Path:
        output_path = Path(output_raw)
        if not output_path.is_absolute():
            output_path = Path(settings.BASE_DIR) / output_path
        return output_path
