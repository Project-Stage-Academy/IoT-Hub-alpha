from django.db import migrations


def enable_timescaledb(apps, schema_editor):
    """Enable TimescaleDB hypertable only if not in test database."""
    db_name = schema_editor.connection.settings_dict["NAME"]

    if "test_" in db_name:
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT create_hypertable(
                'telemetry',
                'timestamp',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE
            );
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp
            ON telemetry (timestamp DESC);
        """
        )


def reverse_timescaledb(apps, schema_editor):
    """Reverse is no-op since we use if_not_exists."""
    db_name = schema_editor.connection.settings_dict["NAME"]

    if "test_" in db_name:
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS idx_telemetry_timestamp;")


class Migration(migrations.Migration):

    dependencies = [
        ("telemetry", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            enable_timescaledb,
            reverse_code=reverse_timescaledb,
        ),
    ]
