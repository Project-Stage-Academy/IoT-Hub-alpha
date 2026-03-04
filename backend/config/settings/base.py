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
    "daphne",
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
    "channels",
    "django_celery_beat",
]

MIDDLEWARE = [
    "request_id.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

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
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Celery
CELERY_BROKER_URL = "redis://redis:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

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

TELEMETRY_ASYNC_INGESTION = os.getenv("TELEMETRY_ASYNC_INGESTION", "false").lower() in (
    "true",
    "1",
    "yes",
)
TELEMETRY_MAX_BATCH_SIZE = int(os.getenv("TELEMETRY_MAX_BATCH_SIZE", "1000"))
TELEMETRY_PIPELINE_MODE = os.getenv("TELEMETRY_PIPELINE_MODE", "direct").strip().lower()
if TELEMETRY_PIPELINE_MODE not in {"direct", "kafka"}:
    raise ValueError(
        "Invalid TELEMETRY_PIPELINE_MODE='"
        f"{TELEMETRY_PIPELINE_MODE}'. Allowed values: direct, kafka"
    )

# DB Writer settings
DB_WRITER_LATENCY_MS = int(os.getenv("DB_WRITER_LATENCY_MS", "1000"))
DB_WRITER_BATCH_SIZE = int(os.getenv("DB_WRITER_BATCH_SIZE", "2000"))
DB_WRITER_MAX_BUFFER_SIZE = int(os.getenv("DB_WRITER_BUFFER_SIZE", "20000"))
DB_WRITER_MAX_FLUSH_ATTEMPTS = int(os.getenv("DB_WRITER_MAX_FLUSH_ATTEMPTS", "3"))
DB_WRITER_SAFETY_SLEEP = float(os.getenv("DB_WRITER_SAFETY_SAFE_SLEEP", "0.01"))
DB_WRITER_CELERY_TIMEOUT_MIN = int(os.getenv("DB_WRITER_CELERY_TIMEOUT_MIN", "600"))
DB_INSERT_BATCH_SIZE = int(os.getenv("DB_INSERT_BATCH_SIZE", "500"))

# Kafka ingestion settings (used when TELEMETRY_PIPELINE_MODE=kafka)
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092").strip()
KAFKA_CLIENT_ID = os.getenv("KAFKA_CLIENT_ID", "iot-hub-backend").strip()
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT").strip()
KAFKA_SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM", "").strip()
KAFKA_SASL_USERNAME = os.getenv("KAFKA_SASL_USERNAME", "").strip()
KAFKA_SASL_PASSWORD = os.getenv("KAFKA_SASL_PASSWORD", "").strip()

KAFKA_TOPIC_TELEMETRY_RAW = os.getenv(
    "KAFKA_TOPIC_TELEMETRY_RAW", "telemetry.raw"
).strip()
KAFKA_TOPIC_TELEMETRY_CLEAN = os.getenv(
    "KAFKA_TOPIC_TELEMETRY_CLEAN", "telemetry.clean"
).strip()
KAFKA_TOPIC_TELEMETRY_DLQ = os.getenv(
    "KAFKA_TOPIC_TELEMETRY_DLQ", "telemetry.dlq"
).strip()
KAFKA_TOPIC_EVENT = os.getenv("KAFKA_TOPIC_EVENT", "event.topic").strip()

KAFKA_PIPELINE_TOPICS = (
    KAFKA_TOPIC_TELEMETRY_RAW,
    KAFKA_TOPIC_TELEMETRY_CLEAN,
    KAFKA_TOPIC_TELEMETRY_DLQ,
    KAFKA_TOPIC_EVENT,
)
if any(not topic for topic in KAFKA_PIPELINE_TOPICS):
    raise ValueError("Kafka topic names must not be empty")
if len(KAFKA_PIPELINE_TOPICS) != len(set(KAFKA_PIPELINE_TOPICS)):
    raise ValueError("Kafka topic names must be unique")

KAFKA_PRODUCER_ACKS = os.getenv("KAFKA_PRODUCER_ACKS", "all").strip()
try:
    KAFKA_PRODUCER_LINGER_MS = int(os.getenv("KAFKA_PRODUCER_LINGER_MS", "20"))
    KAFKA_PRODUCER_BATCH_SIZE = int(os.getenv("KAFKA_PRODUCER_BATCH_SIZE", "65536"))
    KAFKA_REQUEST_TIMEOUT_MS = int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS", "30000"))
    KAFKA_PUBLISH_MAX_RETRIES = int(os.getenv("KAFKA_PUBLISH_MAX_RETRIES", "3"))
    KAFKA_RETRY_BACKOFF_BASE_MS = int(os.getenv("KAFKA_RETRY_BACKOFF_BASE_MS", "100"))
    KAFKA_RETRY_BACKOFF_MAX_MS = int(os.getenv("KAFKA_RETRY_BACKOFF_MAX_MS", "2000"))
    KAFKA_RETRY_BACKOFF_JITTER = float(os.getenv("KAFKA_RETRY_BACKOFF_JITTER", "0.2"))
except ValueError as exc:
    raise ValueError(
        "Kafka numeric settings must be valid numbers "
        "(integers except KAFKA_RETRY_BACKOFF_JITTER which may be float)"
    ) from exc

if KAFKA_PUBLISH_MAX_RETRIES < 0:
    raise ValueError("KAFKA_PUBLISH_MAX_RETRIES must be >= 0")
if KAFKA_RETRY_BACKOFF_BASE_MS < 0:
    raise ValueError("KAFKA_RETRY_BACKOFF_BASE_MS must be >= 0")
if KAFKA_RETRY_BACKOFF_MAX_MS < KAFKA_RETRY_BACKOFF_BASE_MS:
    raise ValueError(
        "KAFKA_RETRY_BACKOFF_MAX_MS must be >= KAFKA_RETRY_BACKOFF_BASE_MS"
    )
if not 0 <= KAFKA_RETRY_BACKOFF_JITTER <= 1:
    raise ValueError("KAFKA_RETRY_BACKOFF_JITTER must be between 0 and 1")
KAFKA_PRODUCER_COMPRESSION_TYPE = os.getenv(
    "KAFKA_PRODUCER_COMPRESSION_TYPE", "none"
).strip()

KAFKA_PRODUCER_CONFIG = {
    "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
    "client.id": KAFKA_CLIENT_ID,
    "security.protocol": KAFKA_SECURITY_PROTOCOL,
    "acks": KAFKA_PRODUCER_ACKS,
    "linger.ms": KAFKA_PRODUCER_LINGER_MS,
    "batch.size": KAFKA_PRODUCER_BATCH_SIZE,
    "compression.type": KAFKA_PRODUCER_COMPRESSION_TYPE,
    "request.timeout.ms": KAFKA_REQUEST_TIMEOUT_MS,
}
if KAFKA_SASL_MECHANISM:
    KAFKA_PRODUCER_CONFIG["sasl.mechanism"] = KAFKA_SASL_MECHANISM
if KAFKA_SASL_USERNAME:
    KAFKA_PRODUCER_CONFIG["sasl.username"] = KAFKA_SASL_USERNAME
if KAFKA_SASL_PASSWORD:
    KAFKA_PRODUCER_CONFIG["sasl.password"] = KAFKA_SASL_PASSWORD

WEBHOOKS_ENABLED = os.getenv("DJANGO_WEBHOOKS_ENABLED", "false").lower() in (
    "true",
    "1",
    "yes",
)
WEBHOOK_TIMEOUT_SECONDS = int(os.getenv("DJANGO_WEBHOOK_TIMEOUT_SECONDS", "5"))

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

# MQTT Adapter settings
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "telemetry/#")
MQTT_QOS = int(os.getenv("MQTT_QOS", "1"))
MQTT_CONNECT_TIMEOUT = int(os.getenv("MQTT_CONNECT_TIMEOUT", "10"))

# Telemetry producer backend: "log" or "kafka".
# If not explicitly provided, derive a sensible default from pipeline mode.
TELEMETRY_PRODUCER_BACKEND = os.getenv("TELEMETRY_PRODUCER_BACKEND", "").strip().lower()
if not TELEMETRY_PRODUCER_BACKEND:
    TELEMETRY_PRODUCER_BACKEND = (
        "kafka" if TELEMETRY_PIPELINE_MODE == "kafka" else "log"
    )
if TELEMETRY_PRODUCER_BACKEND not in {"log", "kafka"}:
    raise ValueError(
        "Invalid TELEMETRY_PRODUCER_BACKEND='"
        f"{TELEMETRY_PRODUCER_BACKEND}'. Allowed values: log, kafka"
    )
if TELEMETRY_PIPELINE_MODE == "kafka" and TELEMETRY_PRODUCER_BACKEND != "kafka":
    raise ValueError(
        "TELEMETRY_PIPELINE_MODE='kafka' requires " "TELEMETRY_PRODUCER_BACKEND='kafka'"
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
