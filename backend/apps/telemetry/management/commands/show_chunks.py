"""
Show TimescaleDB chunks for telemetry table.

Usage:
  python manage.py show_chunks
  docker compose exec -T web python manage.py show_chunks
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Display TimescaleDB chunk information for telemetry hypertable"

    def handle(self, *args, **options):
        """Show chunk details from TimescaleDB."""

        with connection.cursor() as cursor:
            # Get chunk information
            cursor.execute("""
                SELECT
                    chunk_schema,
                    chunk_name,
                    range_start::timestamp as chunk_start,
                    range_end::timestamp as chunk_end,
                    (range_end - range_start) as duration,
                    is_compressed
                FROM timescaledb_information.chunks
                WHERE hypertable_name = 'telemetry'
                ORDER BY range_start
            """)

            chunks = cursor.fetchall()

            if not chunks:
                self.stdout.write("⚠ No chunks found!")
                return

            self.stdout.write("\n" + "="*100)
            self.stdout.write("TimescaleDB Chunks for 'telemetry' Hypertable")
            self.stdout.write("="*100 + "\n")

            for schema, name, start, end, duration, compressed in chunks:
                status = "✓ COMPRESSED" if compressed else "⚬ uncompressed"
                self.stdout.write(f"Chunk: {name}")
                self.stdout.write(f"  Schema: {schema}")
                self.stdout.write(f"  Range: {start} → {end}")
                self.stdout.write(f"  Duration: {duration}")
                self.stdout.write(f"  Status: {status}\n")

            # Show index sizes
            self.stdout.write("\n" + "="*100)
            self.stdout.write("Index Sizes per Chunk")
            self.stdout.write("="*100 + "\n")

            cursor.execute("""
                SELECT
                    t.relname as chunk_name,
                    i.relname as index_name,
                    pg_size_pretty(pg_relation_size(i.oid)) as size
                FROM pg_class t
                JOIN pg_index idx ON t.oid = idx.indrelid
                JOIN pg_class i ON i.oid = idx.indexrelid
                WHERE t.relname LIKE '_hyper_%'
                ORDER BY t.relname, pg_relation_size(i.oid) DESC
            """)

            index_data = cursor.fetchall()

            current_chunk = None
            for chunk_name, index_name, size in index_data:
                if chunk_name != current_chunk:
                    if current_chunk:
                        self.stdout.write("")
                    current_chunk = chunk_name
                    self.stdout.write(f"{chunk_name}:")

                self.stdout.write(f"  {index_name}: {size}")

            # Show record count and data distribution
            self.stdout.write("\n" + "="*100)
            self.stdout.write("Data Distribution")
            self.stdout.write("="*100 + "\n")

            cursor.execute("""
                SELECT
                    COUNT(*) as total_records,
                    MIN(timestamp) as earliest,
                    MAX(timestamp) as latest,
                    COUNT(DISTINCT device_id) as unique_devices
                FROM telemetry
            """)

            result = cursor.fetchone()
            if result:
                total, earliest, latest, devices = result
                self.stdout.write(f"Total Records: {total:,}")
                self.stdout.write(f"Earliest: {earliest}")
                self.stdout.write(f"Latest: {latest}")
                self.stdout.write(f"Unique Devices: {devices}")
            else:
                self.stdout.write("No telemetry data found.")

            # Show compression policy
            self.stdout.write("\n" + "="*100)
            self.stdout.write("Compression & Retention Policies")
            self.stdout.write("="*100 + "\n")

            try:
                cursor.execute("""
                    SELECT
                        id,
                        proc_name,
                        schedule_interval,
                        config::text
                    FROM _timescaledb_config.bgw_job
                    WHERE proc_name IN ('policy_retention', 'policy_compression')
                    ORDER BY id
                """)

                policies = cursor.fetchall()

                if policies:
                    for job_id, proc_name, schedule, config in policies:
                        self.stdout.write(f"Job {job_id}: {proc_name}")
                        self.stdout.write(f"  Schedule: {schedule}")
                        self.stdout.write(f"  Config: {config}\n")
                else:
                    self.stdout.write("No compression or retention policies configured.")
            except Exception as e:
                self.stdout.write(f"⚠ Could not retrieve policies: {str(e)}")

            self.stdout.write("="*100 + "\n")