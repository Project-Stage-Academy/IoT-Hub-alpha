from __future__ import annotations

import json
import os
import argparse
from pathlib import Path
from typing import Any
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.db import transaction
from seed.seed_schema import SeedData, StatsTally
from pydantic import ValidationError
from apps.rules.models import Rule
from apps.notifications.models import NotificationTemplate
from apps.devices.models import DeviceType, Device
from apps.telemetry.models import Telemetry
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = "Seed demo data (idempotent) from backend/seed/*.json"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--file", default="seed/seed_data.json")

        parser.add_argument(
            "--flush",
            action="store_true",
            help="DANGER: flush database before seeding (deletes all data).",
        )

        parser.add_argument(
            "--flush_only",
            action="store_true",
            help="DANGER: flush database, NO seeding with occur with this command",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Mandatory flag to confirm flushing",
        )

        parser.add_argument(
            "--create_superuser",
            action="store_true",
            help="Seed superuser from env variables",
        )

        parser.add_argument(
            "--dry_run",
            action="store_true",
            help="Validate JSON file data and FK references without writing to DB"
            
        )

    def _flush(self, force: bool) -> None:
        if not settings.DEBUG:
            raise CommandError("Flush disabled when settings.DEBUG is False.")
        if not force:
            raise CommandError("Refusing to flush without --force. Example: manage.py seed_data --flush --force")
        call_command("flush", interactive=False)
        self.stdout.write(self.style.SUCCESS("Database flushed successfully"))
    
    def handle(self, *args: Any, **opts: Any) -> None:
        do_flush: bool = opts['flush']
        flush_only: bool = opts['flush_only']
        force: bool = opts['force']
        create_superuser: bool = opts['create_superuser']
        dry_run: bool = opts['dry_run']

        if flush_only and dry_run:
            raise CommandError("--flush_only cannot be combined with --dry_run")
        if do_flush and dry_run:
            raise CommandError("--flush cannot be combined with --dry_run")

        if flush_only:
            self._flush(force)
            return

        if do_flush:
            self._flush(force)
            self.stdout.write(self.style.SUCCESS("Flushed; now seeding…"))

        path: Path = Path(settings.BASE_DIR) / opts["file"]
        if not path.exists():
            raise CommandError(f"Seed file not found: {path}")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON in {path}: {e}") from e
        
        try:
            seed = SeedData.model_validate(data)
        except ValidationError as e:
            raise CommandError(f"Seed validation failed:\n{e}") from e

        if dry_run:
            self._dry_run(seed)
            self.stdout.write(self.style.SUCCESS("JSON is valid"))
            return
        
        stats = StatsTally()

        self._start_seed(seed, create_superuser, stats)

        self.stdout.write(self.style.MIGRATE_HEADING("Seed summary"))
        self.stdout.write(self.style.SUCCESS(
                                             f"Devices - created: {stats.devices.created}, updated: {stats.devices.updated}\n"
                                             f"Device Types - created: {stats.device_types.created}, updated: {stats.device_types.updated}\n"
                                             f"Rules: created - {stats.rules.created}, updated: {stats.rules.updated}\n"
                                             f"Notification templates - created: {stats.notification_templates.created}, updated: {stats.notification_templates.updated}\n"
                                             f"Telemetry: created - {stats.telemetry.created}, updated: {stats.telemetry.updated}\n"
                                             ))

    def _dry_run(self, seed: SeedData):
        d_type_names = {dt.name for dt in seed.device_types}
        d_ssn = {d.serial_number for d in seed.devices}
        errors: list[str] = []

        for dev in seed.devices:
            if dev.device_type not in d_type_names:
                errors.append(
                f"- device '{dev.serial_number}' ('{dev.name}') -> unknown device_type '{dev.device_type}'"
            )
            
        for rule in seed.rules:
            if rule.device not in d_ssn:
                 errors.append(
                f"- rule '{rule.name}' -> unknown device '{rule.device}'"
            )
        
        for telem in seed.telemetry:
            if telem.device not in d_ssn:
                errors.append(
                f"- rule '{telem.device}' -> unknown device '{telem.device}'"
            )

        if errors:
            raise CommandError("Invalid seed JSON cross-references:\n" + "\n".join(errors))
            
        

    @transaction.atomic
    def _start_seed(self, data: SeedData, create_superuser: bool, stats: StatsTally):
        if create_superuser:
            self._seed_super_user()
        device_map = self._seed_device(data, stats)
        notif_map = self._seed_notif_template(data, stats)
        self._seed_rule(data, device_map, notif_map, stats)
        self._seed_telemetry(data, device_map, stats)
        

    def _seed_super_user(self) -> None:
        email = os.getenv("ADMIN_EMAIL", None)
        password = os.getenv("ADMIN_PASSWORD", None)
        username = os.getenv("ADMIN_USERNAME", None)

        if not email or not password:
            raise CommandError("Superuser env vars are missing")

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
            },
            )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS("Superuser created"))
        else:
            changed = False
            for field, val in {"is_staff": True, "is_superuser": True, "is_active": True}.items():
                if getattr(user, field) != val:
                    setattr(user, field, val)
                    changed = True
            if changed:
                self.stdout.write(self.style.SUCCESS("Superuser updated"))
                user.set_password(password)
                user.save(update_fields=["password", "is_staff", "is_superuser", "is_active"])
            else:
                self.stdout.write(self.style.SUCCESS("Superuser already ok"))


    
    def _seed_device(self, data: SeedData, stats: StatsTally) -> dict[str, Device]:
        dt_map: dict[str, DeviceType] = {}
        d_map: dict[str, Device] = {}
        for dt in data.device_types:
            obj_dt, created = DeviceType.objects.update_or_create(
                name=dt.name,
                defaults={
                    "description": dt.description,
                    "metric_name": dt.metric_name,
                    "metric_unit": dt.metric_unit,
                    "metric_min": dt.metric_min,
                    "metric_max": dt.metric_max,
                },
            )
            stats.device_types.add(created=created)
            dt_map[obj_dt.name] = obj_dt

        for d in data.devices:
            dt_name = d.device_type
            if dt_name not in dt_map:
                raise CommandError(f"Unknown device_type '{dt_name}' referenced by device {d}")

            device, created = Device.objects.update_or_create(
                serial_number=d.serial_number,
                defaults={
                    "name": d.name,
                    "location": d.location,
                    "status": d.status,
                    "device_type": dt_map[dt_name],
                },
            )
            stats.devices.add(created=created)
            d_map[device.serial_number] = device
        return d_map


    def _seed_rule(self, data: SeedData, device_map: dict[str, Device], notif_map: dict[str, int], stats: StatsTally) -> None:
        for rule in data.rules:
            device_ref = rule.device
            if device_ref not in device_map:
                raise CommandError(f"Unknown device '{device_ref}' referenced by rule '{rule.name}'")
            for action_conf in rule.action_config:
                if "template_id" in action_conf.model_fields_set:
                    action_conf.template_id = notif_map.get(str(action_conf.template_id))
            action_config_payload = [ac.model_dump(exclude_none=True) for ac in rule.action_config]
            _, created = Rule.objects.update_or_create(
                name=rule.name,
                device=device_map[rule.device],
                defaults={
                    "description": rule.description,
                    "comparison_operator": rule.comparison_operator,
                    "threshold": rule.threshold,
                    "action_config": action_config_payload,
                    "is_enabled": rule.is_enabled
                }
            )
            stats.rules.add(created=created)
        

    def _seed_notif_template(self, data: SeedData, stats: StatsTally) -> dict[str, int]:
        notif_map: dict[str, int] = {}
        for notification in data.notification_templates:
            obj_notif, created = NotificationTemplate.objects.update_or_create(
                name=notification.name,
                defaults={
                    "message_template": notification.message_template,
                    "recipients": notification.recipients,
                    "priority": notification.priority,
                    "retry_count": notification.retry_count,
                    "retry_delay_minutes": notification.retry_delay_minutes,
                    "is_active": notification.is_active,
                }
            )
            stats.notification_templates.add(created=created)
            notif_map[obj_notif.name] = obj_notif.id
        return notif_map
    
    def _seed_telemetry(self, data: SeedData, device_map: dict[str, Device], stats: StatsTally) -> None:
        for telem in data.telemetry:
            if isinstance(telem.payload.value, int):
                telem.payload.value = telem.payload.value / 100
            _, created = Telemetry.objects.update_or_create(
                device_id = device_map[telem.device].id,
                defaults={
                    "payload": telem.payload.model_dump()
                }
            )
            stats.telemetry.add(created=created)