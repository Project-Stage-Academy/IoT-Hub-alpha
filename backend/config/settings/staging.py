from .base import *  # noqa: F403, F401

# Overrides: DEBUG, ALLOWED_HOSTS, DATABASES config, security headers, LOGGING

DEBUG = False

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")  # noqa: F405
if not ALLOWED_HOSTS or ALLOWED_HOSTS == [""]:
    raise ValueError("ALLOWED_HOSTS must be set for staging/production")

if "default" in DATABASES:  # noqa: F405
    DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405
else:
    raise ValueError("DATABASES['default'] not configured in base settings")

SECURE_SSL_REDIRECT = (
    os.getenv("SECURE_SSL_REDIRECT", "True").lower() == "true"
)  # noqa: F405
SESSION_COOKIE_SECURE = (
    os.getenv("SESSION_COOKIE_SECURE", "True").lower() == "true"
)  # noqa: F405
CSRF_COOKIE_SECURE = (
    os.getenv("CSRF_COOKIE_SECURE", "True").lower() == "true"
)  # noqa: F405
SECURE_BROWSER_XSS_FILTER = (
    os.getenv("SECURE_BROWSER_XSS_FILTER", "True").lower() == "true"
)  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = (
    os.getenv("SECURE_CONTENT_TYPE_NOSNIFF", "True").lower() == "true"
)  # noqa: F405
X_FRAME_OPTIONS = os.getenv("X_FRAME_OPTIONS", "DENY")  # noqa: F405

LOGGING = {
    **LOGGING_BASE,  # noqa: F405
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
