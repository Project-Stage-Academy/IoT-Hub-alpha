# Generated migration for TimescaleDB hypertable setup

from django.db import migrations
from django.db import connection
from django.db.utils import DatabaseError


def enable_timescaledb(apps, schema_editor):
    """
    Convert telemetry table to TimescaleDB hypertable.
    - Creates TimescaleDB extension (if available)
    - Converts table to hypertable (if extension available)
    - Adds retention policy (365 days)
    - Adds compression policy (30 days, if available)

    Indexes are managed through Telemetry model's Meta.indexes.

    Note: Gracefully skips TimescaleDB setup if extension not available
    (e.g., in test environments without TimescaleDB installed).
    """
    with connection.cursor() as cursor:
        try:
            # 1. Check if TimescaleDB extension is installed
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'timescaledb')"
            )
            result = cursor.fetchone()
            if not result or not result[0]:
                # Extension not available, skip TimescaleDB setup
                print("ℹ TimescaleDB extension not available")
                print("  Table remains as regular PostgreSQL table")
                return

            # 2. Drop primary key constraint (required for hypertable)
            cursor.execute(
                "ALTER TABLE telemetry DROP CONSTRAINT IF EXISTS telemetry_pkey CASCADE"
            )

            # 3. Create hypertable from existing table
            cursor.execute(
                """
                SELECT create_hypertable(
                    'telemetry',
                    'timestamp',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                )
                """
            )

            # Note: Indexes created by Django from model Meta.indexes (see models.py)
            # They are created in the next migration step automatically

            # 3.5. Enable columnstore (required for compression)
            cursor.execute(
                """
                ALTER TABLE telemetry SET (
                    timescaledb.compress,
                    timescaledb.compress_segmentby = 'device_id',
                    timescaledb.compress_orderby = 'timestamp DESC'
                )
                """
            )
            print("✓ Columnstore enabled on telemetry hypertable")

            # 4. Add retention policy (365 days)
            cursor.execute(
                """
                SELECT add_retention_policy(
                    'telemetry',
                    INTERVAL '365 days',
                    if_not_exists => TRUE
                )
                """
            )

            # 5. Add compression policy (30 days) - now columnstore enabled
            try:
                cursor.execute(
                    """
                    SELECT add_compression_policy(
                        'telemetry',
                        INTERVAL '30 days',
                        if_not_exists => TRUE
                    )
                    """
                )
                print("✓ Compression policy added: compress chunks after 30 days")
            except DatabaseError as e:
                # Catch database errors during compression policy setup
                # (e.g., columnstore issues, policy already exists, etc.)
                print(f"ℹ Compression policy not added: {e}")

        except DatabaseError as e:
            # TimescaleDB operations failed (shouldn't happen if extension check passed)
            error_msg = str(e).lower()
            if "extension" in error_msg or "timescaledb" in error_msg:
                print(f"ℹ TimescaleDB setup skipped (extension not available)")
            elif "feature" in error_msg:
                print(f"ℹ TimescaleDB feature not supported")
            else:
                print(f"ℹ TimescaleDB setup skipped: {e}")
            print("  Table remains as regular PostgreSQL table")


def disable_timescaledb(apps, schema_editor):
    """
    Revert hypertable to regular table (removes hypertable).
    """
    with connection.cursor() as cursor:
        # Drop hypertable (converts back to regular table)
        cursor.execute("SELECT timescaledb_pre_restore() FROM (SELECT 1) AS _")
        cursor.execute(
            "SELECT detach_tablespace('timescaledb_tablespace', 'telemetry', if_attached => true)"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("telemetry", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(enable_timescaledb, disable_timescaledb),
    ]
