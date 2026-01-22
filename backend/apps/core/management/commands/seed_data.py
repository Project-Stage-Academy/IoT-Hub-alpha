from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction
from apps.rules.models import Rule
from apps.devices.models import DeviceType, Device


class Command(BaseCommand):
    help = "Seed demo data (idempotent) from backend/seed/*.json"

    def add_arguments(self, parser):
        parser.add_argument("--file", default="fixtures/seed_data.json")

        parser.add_argument(
            "--flush",
            action="store_true",
            help="DANGER: flush database before seeding (deletes all data).",
        )

        parser.add_argument(
            "--dry_run",
            action="store_true",
            help="Wont write any data to DB NOTE: --flush will still WORK with this tag",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        do_flush: bool = opts['flush']
        dry_run: bool = opts['dry_run']

        if do_flush:
            self.stdout.write(self.style.WARNING("⚠️ Flushing database..."))
            call_command("flush", interactive=False)

        if dry_run:
            self.stdout.write(self.style.SUCCESS("No data was written, dry run enabled"))
            return

        path = Path(settings.BASE_DIR) / opts["file"]
        if not path.exists():
            raise CommandError(f"Seed file not found: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        
        self._seed_device(data)

        self.stdout.write(self.style.SUCCESS("Seed complete"))

    def _seed_device(self, data) -> None:
        dt_map = {}
        for dt in data.get("device_types", []):
            obj, _ = DeviceType.objects.update_or_create(
                name=dt["name"],
                defaults={
                    "description": dt.get("description", ""),
                    "metric_name": dt["metric_name"],
                    "metric_unit": dt["metric_unit"],
                    "metric_min": Decimal(str(dt["metric_min"])),
                    "metric_max": Decimal(str(dt["metric_max"])),
                },
            )
            dt_map[obj.name] = obj

        for d in data.get("devices", []):
            dt_name = d["device_type"]
            if dt_name not in dt_map:
                raise CommandError(f"Unknown device_type '{dt_name}' referenced by device {d}")

            device, _ = Device.objects.update_or_create(
                serial_number=d["serial_number"],
                defaults={
                    "name": d["name"],
                    "location": d.get("location", ""),
                    "status": d.get("status", "active"),
                    "device_type": dt_map[dt_name],
                },
            )
            dt_map[device.name] = device

        for rule in data.get("rules", []):
            dt_device = rule["device"]
            rule, _ = Rule.objects.update_or_create(
                name=rule["name"],
                defaults={
                    "description": rule["description"],
                    "device": dt_map[dt_device],
                    "operator": rule["operator"],
                    "threshold": Decimal(rule["threshold"]),
                    "action_config": rule["action_config"],
                    "cooldown_minutes": rule["cooldown_minutes"],
                    "is_enabled": rule["is_enabled"]
                }
            )


        
