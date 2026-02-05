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
                    chunk_schema,
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

            # Build chunk_sizes dictionary - fetch all sizes in ONE query (optimize N+1)
            chunk_sizes = {}
            if chunks:
                try:
                    # Build dynamic IN clause with proper parameterization
                    chunk_names = [chunk[0] for chunk in chunks]
                    placeholders = ','.join(['%s'] * len(chunk_names))
                    sql = f"""
                        SELECT chunk_name, pg_total_relation_size(
                            (quote_ident(chunk_schema) || '.' || quote_ident(chunk_name))::regclass
                        ) as size
                        FROM timescaledb_information.chunks
                        WHERE hypertable_name = 'telemetry'
                        AND chunk_name IN ({placeholders})
                    """
                    cursor.execute(sql, chunk_names)
                    # Build dictionary: chunk_name -> size_in_mb
                    for chunk_name, size in cursor.fetchall():
                        chunk_sizes[chunk_name] = size / (1024 * 1024)  # Convert to MB
                except Exception as e:
                    # If batch query fails, set all to 0
                    self.stdout.write(
                        self.style.WARNING(f"⚠ Warning: Could not fetch chunk sizes: {str(e)}")
                    )
                    for chunk in chunks:
                        chunk_sizes[chunk[0]] = 0

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
            for chunk_name, _, start, end, _ in chunks:
                size_before = chunk_sizes.get(chunk_name, 0)
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
            for chunk_tuple in chunks:
                chunk_name, chunk_schema, start, end, _ = chunk_tuple
                try:
                    # Build full chunk name safely
                    full_chunk_name = f'"{chunk_schema}"."{chunk_name}"'

                    # Compress the chunk
                    cursor.execute(
                        f"SELECT compress_chunk('{full_chunk_name}')"
                    )
                    cursor.fetchall()  # Clear cursor results

                    # Get size after compression
                    cursor.execute(
                        f"""
                        SELECT pg_total_relation_size(
                            '{full_chunk_name}'::regclass
                        ) as size
                    """
                    )

                    size_result = cursor.fetchone()
                    size_after = size_result[0] / (1024 * 1024) if size_result else 0
                    total_after += size_after

                    # Stored size_before from initial calculation
                    size_before = chunk_sizes.get(chunk_name, 0)

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
