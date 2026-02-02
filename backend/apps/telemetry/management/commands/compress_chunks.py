"""
Manually compress TimescaleDB chunks for telemetry table.

This is useful for testing compression behavior without waiting for scheduled jobs.

Usage:
  # Compress all uncompressed chunks
  python manage.py compress_chunks

  # Compress chunks older than 30 days
  python manage.py compress_chunks --older-than-days=30

  # Dry run (show what would be compressed)
  python manage.py compress_chunks --dry-run

Docker:
  docker compose exec -T web python manage.py compress_chunks
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import connection


class Command(BaseCommand):
    help = "Manually compress TimescaleDB chunks for the telemetry hypertable"

    def add_arguments(self, parser):
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=30,
            help="Only compress chunks older than N days (default: 30)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be compressed without actually compressing",
        )

    def handle(self, *args, **options):
        """Compress chunks."""

        older_than_days = options["older_than_days"]
        dry_run = options["dry_run"]

        with connection.cursor() as cursor:
            # Get uncompressed chunks
            cutoff_time = timezone.now() - timedelta(days=older_than_days)

            cursor.execute(
                """
                SELECT
                    chunk_name,
                    range_start::timestamp as chunk_start,
                    range_end::timestamp as chunk_end,
                    is_compressed
                FROM timescaledb_information.chunks
                WHERE hypertable_name = 'telemetry'
                    AND NOT is_compressed
                    AND range_end::timestamp < %s
                ORDER BY range_start
            """,
                [cutoff_time],
            )

            chunks = cursor.fetchall()

            if not chunks:
                self.stdout.write(
                    self.style.SUCCESS(
                        "No uncompressed chunks older than "
                        f"{older_than_days} days found."
                    )
                )
                return

            self.stdout.write(f"\n{'=' * 80}")
            self.stdout.write("TimescaleDB Chunk Compression")
            self.stdout.write(f"{'=' * 80}\n")

            if dry_run:
                self.stdout.write(
                    self.style.WARNING("DRY RUN - No changes will be made\n")
                )

            self.stdout.write(
                f"Chunks to compress (older than {older_than_days} days):\n"
            )

            total_before = 0
            for chunk_name, start, end, compressed in chunks:
                # Get chunk size before compression
                cursor.execute(
                    """
                    SELECT pg_total_relation_size(
                        format('%I.%I', chunk_schema, %s)::regclass
                    ) as size
                    FROM timescaledb_information.chunks
                    WHERE chunk_name = %s
                    LIMIT 1
                """,
                    [chunk_name, chunk_name],
                )

                size_before = cursor.fetchone()[0] / (1024 * 1024)  # Convert to MB
                total_before += size_before

                self.stdout.write(f"  {chunk_name}")
                self.stdout.write(f"    Range: {start} → {end}")
                self.stdout.write(f"    Size before: {size_before:.2f} MB\n")

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nDRY RUN: Would compress {len(chunks)} chunks "
                        f"({total_before:.2f} MB total)\n"
                    )
                )
                self.stdout.write(f"{'=' * 80}\n")
                return

            # Actually compress the chunks
            self.stdout.write(f"\nCompressing {len(chunks)} chunks...\n")

            total_after = 0
            for chunk_name, start, end, compressed in chunks:
                try:
                    # Get chunk full name (schema.name)
                    cursor.execute(
                        """
                        SELECT format('%I.%I', chunk_schema, chunk_name)::text
                        FROM timescaledb_information.chunks
                        WHERE chunk_name = %s
                        LIMIT 1
                    """,
                        [chunk_name],
                    )

                    full_chunk_name = cursor.fetchone()[0]

                    # Compress the chunk
                    cursor.execute(f"SELECT compress_chunk('{full_chunk_name}')")

                    # Get size after compression
                    cursor.execute(f"""
                        SELECT pg_total_relation_size(
                            '{full_chunk_name}'::regclass
                        ) as size
                    """)

                    size_after = cursor.fetchone()[0] / (1024 * 1024)  # Convert to MB
                    total_after += size_after

                    # Get size before for comparison
                    cursor.execute(
                        """
                        SELECT pg_total_relation_size(
                            format('%I.%I', chunk_schema, %s)::regclass
                        ) as size
                        FROM timescaledb_information.chunks
                        WHERE chunk_name = %s
                        LIMIT 1
                    """,
                        [chunk_name, chunk_name],
                    )

                    size_before = cursor.fetchone()[0] / (1024 * 1024)

                    reduction = (
                        ((size_before - size_after) / size_before * 100)
                        if size_before > 0
                        else 0
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {chunk_name}: {size_before:.2f}MB → "
                            f"{size_after:.2f}MB ({reduction:.1f}% reduction)"
                        )
                    )

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"✗ {chunk_name}: {str(e)}"))

            self.stdout.write(f"\n{'=' * 80}")
            self.stdout.write("Compression Complete")
            self.stdout.write(f"{'=' * 80}")
            self.stdout.write(f"Chunks compressed: {len(chunks)}")
            self.stdout.write(
                f"Total size reduction: {total_before - total_after:.2f} MB"
            )
            if total_before > 0:
                reduction_pct = (total_before - total_after) / total_before * 100
                self.stdout.write(f"Overall reduction: {reduction_pct:.1f}%")
            self.stdout.write(f"{'=' * 80}\n")
