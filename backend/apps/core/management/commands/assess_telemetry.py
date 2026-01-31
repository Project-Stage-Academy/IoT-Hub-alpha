import argparse
from typing import cast
from celery import Task
from django.core.management.base import BaseCommand, CommandError
from typing import Any
from apps.rules.tasks import process_telemetry
from apps.telemetry.models import Telemetry


class Command(BaseCommand):
    help = "Manual initiation of telemetry parser and rule evaluation task"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:

        parser.add_argument(
            "--start",
            type=int,
            help="Telemetry ID for start, if left empty telemetry will"
            "start from Telemetry cursor",
            default=None,
        )

        parser.add_argument(
            "--count",
            type=int,
            default=1000,
            help="Count of telemetries to go over, if left empty it"
            "will process up untill latest telemetry",
        )

        parser.add_argument(
            "--record_cursor",
            action="store_true",
            help="Count of telemetries to go over, if left empty it"
            "will process up untill latest telemetry",
        )

    def handle(self, *args: Any, **opts: Any) -> None:
        start: int | None = opts["start"]
        count: int | None = opts["count"]
        record_cursor: bool = opts["record_cursor"]

        telem_count = Telemetry.objects.count()

        if start and start > telem_count:
            raise CommandError(
                f"Start cannot be higher than total telemetry"
                f"count, current telemetry: {telem_count}"
            )

        self.stdout.write(self.style.SUCCESS(start))

        task = cast(Task, process_telemetry)
        task.delay(cursor_start=start, batch_size=count, record_cursor=record_cursor)
