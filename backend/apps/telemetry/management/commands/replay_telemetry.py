import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.telemetry.serializer import TelemetrySerializer


class Command(BaseCommand):
    help = "Replay telemetry data from a fixture file for debugging and demos"

    def add_arguments(self, parser):
        parser.add_argument(
            "fixture_file",
            type=str,
            help="Path to the JSON fixture file containing telemetry data",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of records to process in each batch (default: 100)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate data without actually creating records",
        )

    def _load_and_validate_fixture(self, fixture_file: str) -> list:
        fixture_path = Path(fixture_file)
        if not fixture_path.exists():
            raise CommandError(f"Fixture file not found: {fixture_file}")

        self.stdout.write(f"Loading telemetry data from {fixture_file}...")

        try:
            with open(fixture_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in fixture file: {e}")

        if not isinstance(data, list):
            raise CommandError(
                "Fixture file must contain a JSON array of telemetry records"
            )
        return data

    def _process_batch_dry_run(self, batch: list, batch_num: int) -> tuple:
        successful = 0
        failed = 0
        errors = []
        for idx, record in enumerate(batch):
            try:
                serializer = TelemetrySerializer(data=record)
                serializer.validate()
                successful += 1
            except Exception as e:
                failed += 1
                errors.append(
                    {
                        "batch": batch_num,
                        "index": idx,
                        "record": record,
                        "error": str(e),
                    }
                )
        return successful, failed, errors

    def _process_batch_save(self, batch: list, batch_num: int) -> tuple:
        successful = 0
        failed = 0
        errors = []
        try:
            with transaction.atomic():
                for idx, record in enumerate(batch):
                    try:
                        serializer = TelemetrySerializer(data=record)
                        serializer.save()
                        successful += 1
                    except Exception as e:
                        failed += 1
                        errors.append(
                            {
                                "batch": batch_num,
                                "index": idx,
                                "record": record,
                                "error": str(e),
                            }
                        )
                        raise
        except Exception:
            self.stdout.write(
                self.style.ERROR(
                    f"Batch {batch_num} failed - rolling back. "
                    f"Fix errors and retry."
                )
            )
        return successful, failed, errors

    def _print_summary(
        self,
        total_records: int,
        successful: int,
        failed: int,
        errors: list,
        dry_run: bool,
    ) -> None:

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(f"Total records: {total_records}")
        self.stdout.write(self.style.SUCCESS(f"Successful: {successful}"))

        if failed > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {failed}"))
            self.stdout.write("\nError details:")
            for error in errors[:10]:
                self.stdout.write(
                    f"  Batch {error['batch']}, Index {error['index']}: "
                    f"{error['error']}"
                )
            if len(errors) > 10:
                self.stdout.write(f"  ... and {len(errors) - 10} more errors")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nDRY RUN completed - no records were created")
            )
        elif failed == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✓ Successfully replayed {successful} telemetry records"
                )
            )
        else:
            raise CommandError(
                f"Replay completed with {failed} errors. "
                f"Check the error details above."
            )

    def handle(self, *args, **options):
        fixture_file = options["fixture_file"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        data = self._load_and_validate_fixture(fixture_file)
        total_records = len(data)
        self.stdout.write(f"Found {total_records} telemetry records")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No records will be created")
            )

        successful = 0
        failed = 0
        errors = []

        for i in range(0, total_records, batch_size):
            batch = data[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_records + batch_size - 1) // batch_size

            self.stdout.write(
                f"Processing batch {batch_num}/{total_batches} "
                f"({len(batch)} records)..."
            )

            if dry_run:
                s, f, e = self._process_batch_dry_run(batch, batch_num)
            else:
                s, f, e = self._process_batch_save(batch, batch_num)

            successful += s
            failed += f
            errors.extend(e)

        self._print_summary(total_records, successful, failed, errors, dry_run)
