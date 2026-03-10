from django.apps import AppConfig


class RulesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rules"

    def ready(self):
        # Register model signal handlers for rule audit logging.
        from .audit import signals  # noqa: F401
