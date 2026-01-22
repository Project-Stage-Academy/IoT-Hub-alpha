import os
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings


class Command(BaseCommand):
    help = "Set up TimescaleDB hypertables and retention policies for telemetry data"

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            self.stdout.write("Setting up TimescaleDB hypertables...")
            
            try:
                cursor.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS events_telemetry_id_e3b31727_fk_telemetry_id CASCADE;")
                self.stdout.write("Dropped foreign key constraint from events")
            except Exception as e:
                self.stdout.write(f"Note: {e}")
            
            try:
                cursor.execute("ALTER TABLE telemetry DROP CONSTRAINT IF EXISTS telemetry_pkey CASCADE;")
                self.stdout.write("Dropped primary key constraint")
            except Exception as e:
                self.stdout.write(f"Note: {e}")
            
            cursor.execute("""
                SELECT create_hypertable(
                    'telemetry',
                    'timestamp',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                );
            """)
            self.stdout.write(self.style.SUCCESS("Created hypertable for telemetry"))
            
            try:
                cursor.execute("""
                    ALTER TABLE events 
                    ADD CONSTRAINT events_telemetry_id_fk 
                    FOREIGN KEY (telemetry_id) REFERENCES telemetry(id);
                """)
                self.stdout.write("Re-created foreign key constraint on events")
            except Exception as e:
                self.stdout.write(f"Note: Could not re-create FK: {e}")
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_telemetry_payload_gin 
                ON telemetry USING gin (payload);
            """)
            self.stdout.write(self.style.SUCCESS("Created GIN index on payload JSONB column"))
            
            # Get retention days from settings or environment
            retention_days = getattr(settings, 'TELEMETRY_RETENTION_DAYS', 
                              int(os.getenv('TELEMETRY_RETENTION_DAYS', '365')))
            
            cursor.execute(f"""
                SELECT add_retention_policy(
                    'telemetry',
                    INTERVAL '{retention_days} days',
                    if_not_exists => TRUE
                );
            """)
            self.stdout.write(
                self.style.SUCCESS(f"Added retention policy: {retention_days} days")
            )
            
            try:
                # Use 30 days compression as per documentation
                compression_days = 30
                cursor.execute(f"""
                    SELECT add_compression_policy(
                        'telemetry',
                        INTERVAL '{compression_days} days',
                        if_not_exists => TRUE
                    );
                """)
                self.stdout.write(
                    self.style.SUCCESS(f" Added compression policy for data older than {compression_days} days")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f" Compression policy not added (columnstore not enabled): {e}")
                )
            
            self.stdout.write(
                self.style.SUCCESS("\n TimescaleDB setup completed successfully!")
            )
            