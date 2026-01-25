from .base import *  # noqa: F403, F401

# Overrides: DEBUG, ALLOWED_HOSTS, DATABASES["default"]["CONN_MAX_AGE"], LOGGING

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

if "default" in DATABASES:  # noqa: F405
    DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
else:
    raise ValueError("DATABASES['default'] not configured in base settings")

LOGGING = {
    **LOGGING_BASE,  # noqa: F405
    "loggers": {
        **LOGGING_BASE.get("loggers", {}),  # noqa: F405
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": True,
        },
        "django.db.backends.schema": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": True,
        },
    },
}
