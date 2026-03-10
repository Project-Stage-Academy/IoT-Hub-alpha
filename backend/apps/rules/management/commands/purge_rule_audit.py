from __future__ import annotations

import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.rules.models import RuleAuditLog


class Command(BaseCommand):
    help = "Purge rule audit logs older than retention threshold"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help=(
                "Retention period in days. "
                "Defaults to RULE_AUDIT_RETENTION_DAYS env var or 180."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be removed without deleting them",
        )

    def handle(self, *args, **options):
        retention_days = options.get("days")
        if retention_days is None:
            retention_days = int(os.getenv("RULE_AUDIT_RETENTION_DAYS", "180"))

        if retention_days < 1:
            raise CommandError("days must be >= 1")

        cutoff = timezone.now() - timedelta(days=retention_days)
        queryset = RuleAuditLog.objects.filter(created_at__lt=cutoff)
        candidates = queryset.count()

        if options.get("dry_run"):
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: would delete "
                    f"{candidates} rule audit row(s) older than {cutoff.isoformat()}"
                )
            )
            return

        deleted_count, _ = queryset.delete()
        self.stdout.write(
            self.style.SUCCESS(
                "Deleted "
                f"{deleted_count} rule audit row(s) older than {cutoff.isoformat()}"
            )
        )
