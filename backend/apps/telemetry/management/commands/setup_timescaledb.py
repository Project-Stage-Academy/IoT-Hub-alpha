import os
import logging
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
from psycopg2 import ProgrammingError, OperationalError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up TimescaleDB hypertables and retention policies for telemetry data"

    def _drop_constraints(self, cursor):
        """Drop primary key constraint before creating hypertable."""
        try:
            cursor.execute(
                "ALTER TABLE telemetry DROP CONSTRAINT IF EXISTS "
                "telemetry_pkey CASCADE;"
            )
            self.stdout.write("Dropped primary key constraint")
        except Exception as e:
            logger.warning(f"Failed to drop primary key constraint: {e}", exc_info=True)
            self.stdout.write(self.style.WARNING(f"Note: {e}"))
            if not isinstance(e, (ProgrammingError, OperationalError)):
                raise

    def _create_hypertable(self, cursor):
        """Create TimescaleDB hypertable for telemetry data."""
        cursor.execute(
            """
            SELECT create_hypertable(
                'telemetry',
                'timestamp',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
        """
        )
        self.stdout.write(self.style.SUCCESS("Created hypertable for telemetry"))

    def _create_indexes(self, cursor):
        """Create necessary indexes for telemetry data."""
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_telemetry_payload_gin
            ON telemetry USING gin (payload);
        """
        )
        self.stdout.write(
            self.style.SUCCESS("Created GIN index on payload JSONB column")
        )

    def _configure_retention(self, cursor):
        """Configure data retention policy for telemetry."""
        retention_days = getattr(
            settings,
            "TELEMETRY_RETENTION_DAYS",
            int(os.getenv("TELEMETRY_RETENTION_DAYS", "365")),
        )

        cursor.execute(
            """
            SELECT add_retention_policy(
                'telemetry',
                INTERVAL %s,
                if_not_exists => TRUE
            );
        """,
            [f"{retention_days} days"],
        )
        self.stdout.write(
            self.style.SUCCESS(f"Added retention policy: {retention_days} days")
        )

    def _configure_compression(self, cursor):
        """Configure compression policy for telemetry data."""
        try:
            compression_days = getattr(
                settings,
                "TELEMETRY_COMPRESSION_DAYS",
                int(os.getenv("TELEMETRY_COMPRESSION_DAYS", "30")),
            )
            cursor.execute(
                """
                SELECT add_compression_policy(
                    'telemetry',
                    INTERVAL %s,
                    if_not_exists => TRUE
                );
            """,
                [f"{compression_days} days"],
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Added compression policy for data older than "
                    f"{compression_days} days"
                )
            )
        except Exception as e:
            logger.info(
                f"Compression policy not added (likely columnstore not enabled): {e}"
            )
            self.stdout.write(
                self.style.WARNING(
                    f"Compression policy not added " f"(columnstore not enabled): {e}"
                )
            )

    def handle(self, *args, **options):
        """Main entry point for TimescaleDB setup."""
        with connection.cursor() as cursor:
            self.stdout.write("Setting up TimescaleDB hypertables...")

            self._drop_constraints(cursor)
            self._create_hypertable(cursor)
            self._create_indexes(cursor)
            self._configure_retention(cursor)
            self._configure_compression(cursor)

            self.stdout.write(
                self.style.SUCCESS("\nTimescaleDB setup completed successfully!")
            )
