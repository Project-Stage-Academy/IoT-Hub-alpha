import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or "insecure" in SECRET_KEY.lower():
    raise ValueError("SECRET_KEY must be set to a secure value")

DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.devices",
    "apps.telemetry",
    "apps.rules",
    "apps.events",
    "apps.notifications",
    "django_celery_beat",
]

MIDDLEWARE = [
    "request_id.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.RateLimitingMiddleware",
    "config.middleware.RequestContextMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "iot_hub_alpha_db"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", "postgres"),
        "HOST": os.getenv("DB_HOST", "db"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        "OPTIONS": {
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        },
    }
}

TIME_ZONE = "UTC"  # or your TZ
USE_TZ = True

if os.getenv("DB_CONN_HEALTH_CHECKS", "False").lower() == "true":
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".UserAttributeSimilarityValidator"
        ),
    },
    {"NAME": ("django.contrib.auth.password_validation" ".MinimumLengthValidator",)},
    {"NAME": ("django.contrib.auth.password_validation" ".CommonPasswordValidator",)},
    {"NAME": ("django.contrib.auth.password_validation" ".NumericPasswordValidator",)},
]


#Celery
CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_TIMER = int(os.getenv("CELERY_RUN_PROCESS_TELEMETRY_TIMER_MINUTES", 5))*60

CELERY_BEAT_SCHEDULE = {
    "run-rule-processor-every-5m": {
        "task": "apps.rules.tasks.process_telemetry",
        "schedule": CELERY_TIMER
    }
}

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

from .telemetry import TELEMETRY_RETENTION_DAYS  # noqa: E402

LOGGING_BASE = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {"()": "config.logging.RequestContextFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "fmt": (
                "%(asctime)s %(levelname)s %(name)s %(message)s "
                "%(request_id)s %(request_method)s %(request_path)s "
                "%(task_id)s %(task_name)s"
            ),
            "rename_fields": {
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_context"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "level": "ERROR",
            "propagate": True,
        },
        "django.server": {
            "level": "INFO",
            "propagate": True,
        },
        "celery": {
            "level": "INFO",
            "propagate": True,
        },
        "celery.task": {
            "level": "INFO",
            "propagate": True,
        },
        "apps.rules": {
            "level": "INFO",
            "propagate": True,
        },
    },
}

# Set LOGGING to use LOGGING_BASE by default
# (can be overridden in local.py and staging.py if needed)
LOGGING = LOGGING_BASE

# Celery (defaults for local compose)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

TELEMETRY_ASYNC_INGESTION = os.getenv("TELEMETRY_ASYNC_INGESTION", "false").lower() in ("true", "1", "yes")
TELEMETRY_MAX_BATCH_SIZE = int(os.getenv("TELEMETRY_MAX_BATCH_SIZE", "1000"))

REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
REQUEST_ID_RESPONSE_HEADER = "X-Request-ID"
REQUEST_ID_GENERATOR = "request_id.uuid4"

try:
    from config.logging import setup_celery_logging_context  # noqa: E402
except ImportError as exc:
    logging.getLogger(__name__).exception(
        "logging.setup_celery_logging_context_import_failed",
        extra={"error": str(exc)},
    )
    setup_celery_logging_context = None

if callable(setup_celery_logging_context):
    setup_celery_logging_context()
elif setup_celery_logging_context is not None:
    logging.getLogger(__name__).warning(
        "logging.setup_celery_logging_context_not_callable",
        extra={"type": type(setup_celery_logging_context).__name__},
    )

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "False").lower() in (
    "true",
    "1",
    "yes",
)

# Default limits for most API endpoints
RATE_LIMIT_DEFAULT_COUNT = int(os.getenv("RATE_LIMIT_DEFAULT_COUNT", "60"))
RATE_LIMIT_DEFAULT_PERIOD = int(
    os.getenv("RATE_LIMIT_DEFAULT_PERIOD", "60")
)  # in seconds

# Stricter limits for admin login and other sensitive admin actions
RATE_LIMIT_ADMIN_COUNT = int(os.getenv("RATE_LIMIT_ADMIN_COUNT", "20"))
RATE_LIMIT_ADMIN_PERIOD = int(os.getenv("RATE_LIMIT_ADMIN_PERIOD", "60"))

# Generous limits for high-frequency device telemetry ingestion
RATE_LIMIT_DEVICE_COUNT = int(os.getenv("RATE_LIMIT_DEVICE_COUNT", "100"))
RATE_LIMIT_DEVICE_PERIOD = int(os.getenv("RATE_LIMIT_DEVICE_PERIOD", "60"))
