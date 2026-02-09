from .base import *  # noqa: F403, F401

# Overrides: DEBUG, ALLOWED_HOSTS, DATABASES["default"]["CONN_MAX_AGE"], LOGGING

DEBUG = True
REQUEST_ID_GENERATOR = "uuid.uuid4"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "web"]

CSRF_TRUSTED_ORIGINS = [
    "https://localhost",
    "https://127.0.0.1",
    "http://localhost",
    "http://127.0.0.1",
]

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
