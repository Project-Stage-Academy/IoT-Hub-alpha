import os
from django.test import TestCase
from django.conf import settings


class SettingsConfigurationTest(TestCase):
    def test_database_config_from_env(self):
        """Verify database reads from environment variables"""
        self.assertIn("default", settings.DATABASES)
        db_config = settings.DATABASES["default"]
        self.assertEqual(db_config["ENGINE"], "django.db.backends.postgresql")
        self.assertIsNotNone(db_config["NAME"])

    def test_telemetry_retention_configured(self):
        """Verify TimescaleDB-specific settings are present"""
        self.assertTrue(hasattr(settings, "TELEMETRY_RETENTION_DAYS"))
        self.assertIsInstance(settings.TELEMETRY_RETENTION_DAYS, int)

    def test_settings_module_structure(self):
        """Verify modular settings structure works"""
        self.assertTrue(settings.configured)

    def test_database_connection_timeout(self):
        """Verify DB connection timeout is configurable"""
        db_config = settings.DATABASES["default"]
        self.assertIn("OPTIONS", db_config)
        self.assertIn("connect_timeout", db_config["OPTIONS"])
        self.assertIsInstance(db_config["OPTIONS"]["connect_timeout"], int)

    def test_database_health_checks_configurable(self):
        """Verify DB health checks can be enabled via environment"""
        db_config = settings.DATABASES["default"]
        if os.getenv("DB_CONN_HEALTH_CHECKS", "False").lower() == "true":
            self.assertTrue(db_config.get("CONN_HEALTH_CHECKS", False))

    def test_secret_key_validation(self):
        """Verify SECRET_KEY is set and not insecure"""
        self.assertTrue(hasattr(settings, "SECRET_KEY"))
        self.assertIsNotNone(settings.SECRET_KEY)
        self.assertNotIn("insecure", settings.SECRET_KEY.lower())

    def test_logging_base_exists(self):
        """Verify LOGGING_BASE is available for environment-specific overrides"""
        self.assertTrue(hasattr(settings, "LOGGING_BASE"))
        self.assertIn("version", settings.LOGGING_BASE)
        self.assertIn("handlers", settings.LOGGING_BASE)
