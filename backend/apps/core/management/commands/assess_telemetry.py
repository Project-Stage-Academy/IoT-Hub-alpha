import argparse
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max
from django.utils import timezone
from typing import Any

from apps.rules.tasks import process_telemetry
from apps.telemetry.models import Telemetry


class Command(BaseCommand):
    help = "Manually enqueue telemetry parser + rule evaluation task"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--start",
            type=int,
            default=None,
            help="Start telemetry ID (exclusive). If omitted, uses cursor.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="How many telemetry rows to process this run.",
        )
        parser.add_argument(
            "--no-record-cursor",
            action="store_false",
            help="If set, persist cursor after processing (dangerous in replays).",
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        start: int | None = opts["start"]
        batch_size: int = opts["batch_size"]
        update_cursor: bool = opts["no_record_cursor"]

        max_id = Telemetry.objects.aggregate(m=Max("id"))["m"] or 0

        if start is not None and start > max_id:
            raise CommandError(
                f"--start ({start}) cannot exceed max telemetry id ({max_id})."
            )

        result = process_telemetry.delay(
            cursor_start=start,
            batch_size=batch_size,
            record_cursor=update_cursor,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"[{timezone.now().isoformat()}] Enqueued"
                f"process_telemetry task id={result.id} "
                f"(start={start}, batch_size={batch_size},"
                f" record_cursor={update_cursor})"
            )
        )
