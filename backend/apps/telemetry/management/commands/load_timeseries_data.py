"""
Management command to load large-scale telemetry data directly to database.

Uses raw SQL INSERT to bypass Django ORM auto_now_add constraint,
allowing custom historical timestamps for TimescaleDB testing.

Usage:
  # Load 100K records over 90 days (to see multiple chunks)
  python manage.py load_timeseries_data --count=100000 --days-back=90

  # Load 500K records over 120 days (to see compression kick in)
  python manage.py load_timeseries_data --count=500000 --days-back=120

  # Load with historical data (simulates months of backlog)
  python manage.py load_timeseries_data --count=200000 --days-back=180 --batch-size=5000

Docker:
  docker compose exec -T web \
    python manage.py load_timeseries_data --count=100000 --days-back=90
"""

import sys
import json
import random
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import connection
from apps.devices.models import Device, DeviceType


class Command(BaseCommand):
    help = "Load large-scale telemetry data directly to database using raw SQL"

    # Realistic value ranges for different metric types
    METRIC_RANGES = {
        "temperature": {"min": 15.0, "max": 85.0, "unit": "°C"},
        "vibration": {"min": 0.0, "max": 25.0, "unit": "mm/s"},
        "pressure": {"min": 0.8, "max": 1.2, "unit": "bar"},
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=100000,
            help="Number of telemetry records to generate (default: 100000)",
        )
        parser.add_argument(
            "--days-back",
            type=int,
            default=90,
            help="Number of days back to backfill data (default: 90)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for bulk_create operations (default: 1000)",
        )
        parser.add_argument(
            "--verbose", action="store_true", help="Enable verbose output"
        )

    def log(self, message):
        """Print message always (not dependent on verbose)."""
        self.stdout.write(message)

    def vlog(self, message):
        """Print message only if verbose mode is enabled."""
        if self.verbose:
            self.stdout.write(f"[VERBOSE] {message}")

    def ensure_test_devices(self):
        """Create or get test devices and device types."""
        self.vlog("Checking for test devices...")

        # Create device types if missing
        device_types = {}
        for metric_type in ["temperature", "vibration", "pressure"]:
            dt, created = DeviceType.objects.get_or_create(
                name=f"Test {metric_type.title()} Sensor",
                defaults={
                    "description": f"Auto-generated test {metric_type} sensor",
                    "metric_name": metric_type,
                    "metric_unit": self.METRIC_RANGES[metric_type]["unit"],
                    "metric_min": Decimal(str(self.METRIC_RANGES[metric_type]["min"])),
                    "metric_max": Decimal(str(self.METRIC_RANGES[metric_type]["max"])),
                },
            )
            device_types[metric_type] = dt
            if created:
                self.vlog(f"Created DeviceType: {dt.name}")

        # Create test devices
        devices = []
        for i in range(3):
            for metric_type in ["temperature", "vibration", "pressure"]:
                device_name = f"Load-Test-{metric_type.title()}-{i + 1}"
                device, created = Device.objects.get_or_create(
                    serial_number=f"LOADTEST-{metric_type.upper()}-{i + 1}",
                    defaults={
                        "name": device_name,
                        "device_type": device_types[metric_type],
                        "location": f"Test Rack {i + 1}",
                        "status": Device.DeviceStatus.ACTIVE,
                    },
                )
                devices.append(device)
                if created:
                    self.vlog(f"Created Device: {device.name}")

        self.vlog(f"Using {len(devices)} test devices")
        return devices

    def generate_telemetry_batch(self, device, count, start_time, end_time):
        """Generate telemetry records for a device across a time range."""
        batch = []
        device_type = device.device_type
        metric_type = device_type.metric_name
        metric_range = self.METRIC_RANGES.get(metric_type, {})

        min_val = metric_range.get("min", 0)
        max_val = metric_range.get("max", 100)

        # Generate timestamps evenly distributed across the range
        time_delta = (end_time - start_time) / max(count - 1, 1)

        for i in range(count):
            # Generate timestamp
            current_time = start_time + (
                timedelta(seconds=time_delta.total_seconds()) * i
            )

            # Generate realistic value with some variation
            if i > 0:
                prev_value = batch[i - 1]["payload"]["value"]
                change = random.uniform(-2, 2)
                value = max(min_val, min(max_val, prev_value + change))
            else:
                value = random.uniform(min_val, max_val)

            # Create telemetry record dict (not ORM object)
            batch.append(
                {
                    "device_id": device.id,
                    "timestamp": current_time,
                    "payload": {
                        "version": "0.0.1",
                        "serial_number": device.serial_number,
                        "value": round(value, 2),
                        "metric_type": metric_type,
                        "unit": metric_range.get("unit", ""),
                    },
                }
            )

        return batch

    def handle(self, *args, **options):
        """Main handler."""
        self.verbose = options["verbose"]
        total_count = options["count"]
        days_back = options["days_back"]
        batch_size = options["batch_size"]

        # Get or create devices
        devices = self.ensure_test_devices()

        # Calculate time range
        end_time = timezone.now()
        start_time = end_time - timedelta(days=days_back)

        self.log(f"\n{'=' * 70}")
        self.log("Telemetry Data Load Configuration")
        self.log(f"{'=' * 70}")
        self.log(f"Total Records to Generate: {total_count:,}")
        self.log(f"Batch Size: {batch_size:,}")
        self.log(
            f"Time Range: {start_time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"to {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.log(f"Span: {days_back} days")
        self.log(f"Number of Test Devices: {len(devices)}")
        records_per_device = total_count // len(devices)
        self.log(f"Records per Device (approx): {records_per_device:,}")
        self.log(f"{'=' * 70}\n")

        # Generate and insert in batches
        total_batches = (total_count + batch_size - 1) // batch_size
        telemetry_created = 0

        try:
            with connection.cursor() as cursor:
                for batch_num in range(total_batches):
                    records_in_batch = min(
                        batch_size, total_count - (batch_num * batch_size)
                    )
                    records_per_device_batch = records_in_batch // len(devices)

                    # Divide time range across batches
                    batch_progress = batch_num / total_batches
                    batch_start = start_time + (end_time - start_time) * batch_progress
                    batch_end = (
                        start_time +
                        (end_time - start_time) * (batch_num + 1) / total_batches
                    )

                    # DEBUG: Show time range for selected batches
                    if (batch_num == 0 or
                            batch_num == total_batches // 2 or
                            batch_num == total_batches - 1):
                        self.vlog(f"Batch {batch_num}: {batch_start} → {batch_end}")

                    all_telemetry = []

                    for device in devices:
                        batch_data = self.generate_telemetry_batch(
                            device=device,
                            count=records_per_device_batch,
                            start_time=batch_start,
                            end_time=batch_end,
                        )
                        all_telemetry.extend(batch_data)

                    # Insert batch using raw SQL (bypasses auto_now_add=True)
                    # Use multiple VALUES in single query for speed (like bulk_create)
                    if all_telemetry:
                        # Build a single INSERT with all values
                        placeholders = []
                        params = []
                        for record in all_telemetry:
                            placeholders.append("(%s, %s, %s)")
                            params.append(record["device_id"])
                            params.append(record["timestamp"])
                            params.append(json.dumps(record["payload"]))

                        sql = f"""
                            INSERT INTO telemetry (device_id, timestamp, payload)
                            VALUES {', '.join(placeholders)}
                        """
                        cursor.execute(sql, params)

                    telemetry_created += len(all_telemetry)

                    progress = (batch_num + 1) / total_batches * 100
                    self.log(
                        f"[{progress:6.1f}%] Batch {batch_num + 1}/{total_batches}: "
                        f"Created {len(all_telemetry):,} records. "
                        f"Total: {telemetry_created:,}"
                    )

            self.log(f"\n{'=' * 70}")
            self.log("✓ Data Load Complete")
            self.log(f"{'=' * 70}")
            self.log(f"Total Records Created: {telemetry_created:,}")
            self.log(f"Time Range: {start_time.date()} to {end_time.date()}")
            self.log(f"Devices: {len(devices)}")
            self.log("\nNext Steps:")
            self.log("  1. View chunks: python manage.py show_chunks")
            self.log("  2. Compress: python manage.py compress_chunks")
            self.log(f"{'=' * 70}\n")

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error during data load: {e}"))
            if self.verbose:
                import traceback

                traceback.print_exc()
            sys.exit(1)
