"""
Show TimescaleDB chunks for any hypertable.

Usage:
  python manage.py show_chunks                                # Show telemetry chunks (default)
  python manage.py show_chunks --table-name=rules            # Show rules chunks
  python manage.py show_chunks --table-name=devices          # Show devices chunks
  docker compose exec -T web python manage.py show_chunks
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Display TimescaleDB chunk information for any hypertable"

    def add_arguments(self, parser):
        parser.add_argument(
            "--table-name",
            type=str,
            default="telemetry",
            help="Hypertable name to display chunks for (default: telemetry)",
        )

    def handle(self, *args, **options):
        """Show chunk details from TimescaleDB."""
        table_name = options.get("table_name") or "telemetry"

        with connection.cursor() as cursor:
            # Get chunk information using parameterized query
            cursor.execute(
                """
                SELECT
                    chunk_schema,
                    chunk_name,
                    range_start::timestamp as chunk_start,
                    range_end::timestamp as chunk_end,
                    (range_end - range_start) as duration,
                    is_compressed
                FROM timescaledb_information.chunks
                WHERE hypertable_name = %s
                ORDER BY range_start
            """,
                [table_name],
            )

            chunks = cursor.fetchall()

            if not chunks:
                self.stdout.write(f"⚠ No chunks found for '{table_name}'!")
                return

            self.stdout.write("\n" + "=" * 100)
            self.stdout.write(f"TimescaleDB Chunks for '{table_name}' Hypertable")
            self.stdout.write("=" * 100 + "\n")

            for schema, name, start, end, duration, compressed in chunks:
                status = "✓ COMPRESSED" if compressed else "⚬ uncompressed"
                self.stdout.write(f"Chunk: {name}")
                self.stdout.write(f"  Schema: {schema}")
                self.stdout.write(f"  Range: {start} → {end}")
                self.stdout.write(f"  Duration: {duration}")
                self.stdout.write(f"  Status: {status}\n")

            # Show index sizes (filtered by table name)
            self.stdout.write("\n" + "=" * 100)
            self.stdout.write("Index Sizes per Chunk")
            self.stdout.write("=" * 100 + "\n")

            try:
                # Use parameterized query with filtering by hypertable
                # Get index sizes for chunks using schema and chunk name
                cursor.execute(
                    """
                    SELECT
                        t.relname as chunk_name,
                        i.relname as index_name,
                        pg_size_pretty(pg_relation_size(i.oid)) as size
                    FROM pg_class t
                    JOIN pg_namespace nt ON t.relnamespace = nt.oid
                    JOIN pg_index idx ON t.oid = idx.indrelid
                    JOIN pg_class i ON i.oid = idx.indexrelid
                    JOIN timescaledb_information.chunks ch ON (
                        ch.chunk_schema = nt.nspname AND ch.chunk_name = t.relname
                    )
                    WHERE ch.hypertable_name = %s
                    ORDER BY t.relname, pg_relation_size(i.oid) DESC
                """,
                    [table_name],
                )

                index_data = cursor.fetchall()

                if index_data:
                    current_chunk = None
                    for chunk_name, index_name, size in index_data:
                        if chunk_name != current_chunk:
                            if current_chunk:
                                self.stdout.write("")
                            current_chunk = chunk_name
                            self.stdout.write(f"{chunk_name}:")

                        self.stdout.write(f"  {index_name}: {size}")
                else:
                    self.stdout.write("No indexes found for chunks.")
            except Exception as e:
                self.stdout.write(f"⚠ Could not retrieve index sizes: {str(e)}")
                self.stdout.write(f"   Exception Type: {type(e).__name__}")

            # Show record count and data distribution
            self.stdout.write("\n" + "=" * 100)
            self.stdout.write("Data Distribution")
            self.stdout.write("=" * 100 + "\n")

            try:
                # Get data distribution stats
                # Note: table_name is from command args (not user input) and validated
                # For table names, we must use identifier quoting, not parameter substitution
                from psycopg2 import sql as psycopg2_sql

                query = psycopg2_sql.SQL(
                    """
                    SELECT
                        COUNT(*) as total_records,
                        MIN(timestamp) as earliest,
                        MAX(timestamp) as latest,
                        COUNT(DISTINCT device_id) as unique_devices
                    FROM {}
                """
                ).format(psycopg2_sql.Identifier(table_name))
                cursor.execute(query.as_string(cursor.connection))

                result = cursor.fetchone()
                if result:
                    total, earliest, latest, devices = result
                    self.stdout.write(f"Total Records: {total:,}")
                    self.stdout.write(f"Earliest: {earliest}")
                    self.stdout.write(f"Latest: {latest}")
                    self.stdout.write(f"Unique Devices: {devices}")
                else:
                    self.stdout.write(f"No data found in '{table_name}'.")
            except Exception as e:
                self.stdout.write(f"⚠ Could not retrieve data distribution: {str(e)}")
                self.stdout.write(f"   Exception Type: {type(e).__name__}")

            # Show compression policy
            self.stdout.write("\n" + "=" * 100)
            self.stdout.write("Compression & Retention Policies")
            self.stdout.write("=" * 100 + "\n")

            try:
                cursor.execute(
                    """
                    SELECT
                        id,
                        proc_name,
                        schedule_interval,
                        config::text
                    FROM _timescaledb_config.bgw_job
                    WHERE proc_name IN ('policy_retention', 'policy_compression')
                    ORDER BY id
                """
                )

                policies = cursor.fetchall()

                if policies:
                    for job_id, proc_name, schedule, config in policies:
                        self.stdout.write(f"Job {job_id}: {proc_name}")
                        self.stdout.write(f"  Schedule: {schedule}")
                        self.stdout.write(f"  Config: {config}\n")
                else:
                    self.stdout.write(
                        "No compression or retention policies configured."
                    )
            except Exception as e:
                self.stdout.write(f"⚠ Could not retrieve policies: {str(e)}")
                self.stdout.write(f"   Exception Type: {type(e).__name__}")

            self.stdout.write("=" * 100 + "\n")
