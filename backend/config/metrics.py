"""Prometheus metrics for monitoring Django application and Celery tasks."""

from prometheus_client import Counter, Histogram, Gauge

# HTTP Request Metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0),
)

# Database Connection Metrics
DB_CONNECTIONS = Gauge(
    "django_db_connections_active",
    "Number of active database connections",
    ["database"],
)

# Celery Queue Metrics
CELERY_QUEUE_LENGTH = Gauge(
    "celery_queue_length",
    "Number of tasks in Celery queue",
    ["queue_name"],
)

CELERY_TASKS_TOTAL = Counter(
    "celery_tasks_total",
    "Total Celery tasks processed",
    ["task_name", "status"],
)

CELERY_TASK_DURATION_SECONDS = Histogram(
    "celery_task_duration_seconds",
    "Celery task execution duration",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0),
)