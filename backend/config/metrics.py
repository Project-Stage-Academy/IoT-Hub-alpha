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

# Ingestion pipeline metrics
INGEST_MESSAGES_TOTAL = Counter(
    "ingest_messages_total",
    "Total ingestion messages by pipeline stage",
    ["stage", "protocol", "status"],
)

INGEST_ERRORS_TOTAL = Counter(
    "ingest_errors_total",
    "Total ingestion errors",
    ["component", "error_type", "protocol"],
)

INGEST_LATENCY_SECONDS = Histogram(
    "ingest_latency_seconds",
    "Ingestion latency by stage in seconds",
    ["stage", "protocol"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

BUFFER_FILL_RATIO = Gauge(
    "buffer_fill_ratio",
    "Buffer fill ratio from 0.0 to 1.0",
    ["component"],
)

KAFKA_CONSUMER_LAG = Gauge(
    "kafka_consumer_lag",
    "Kafka consumer lag by topic and group",
    ["topic", "group"],
)