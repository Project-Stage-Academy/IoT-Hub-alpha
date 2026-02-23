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

# ============================================================================
# RULE ENGINE METRICS
# ============================================================================

# Rule Evaluation Metrics
RULE_EVALUATION_DURATION_MS = Histogram(
    "rule_evaluation_duration_ms",
    "Time taken to evaluate a single rule in milliseconds",
    ["rule_id", "device_id", "operator"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0),
)

RULES_EVALUATED_TOTAL = Counter(
    "rules_evaluated_total",
    "Total number of rules evaluated",
    ["rule_id", "device_id", "result"],  # result: triggered, skipped
)

RULES_TRIGGERED_TOTAL = Counter(
    "rules_triggered_total",
    "Total number of rules that triggered",
    ["rule_id", "device_id"],
)

RULE_EVALUATION_ERRORS = Counter(
    "rule_evaluation_errors_total",
    "Total rule evaluation errors",
    [
        "rule_id",
        "error_type",
    ],  # error_type: invalid_condition, invalid_threshold, db_error
)

# Event Metrics
EVENTS_CREATED_TOTAL = Counter(
    "events_created_total",
    "Total events created",
    ["rule_id", "device_id"],
)

EVENTS_COOLDOWN_SKIPPED = Counter(
    "events_cooldown_skipped_total",
    "Events skipped due to cooldown period",
    ["rule_id", "device_id"],
)

EVENT_CREATION_DURATION_MS = Histogram(
    "event_creation_duration_ms",
    "Time taken to create an event in milliseconds",
    ["rule_id"],
    buckets=(1.0, 5.0, 10.0, 50.0, 100.0, 500.0),
)

# Kafka Consumer Metrics
KAFKA_MESSAGES_PROCESSED = Counter(
    "kafka_messages_processed_total",
    "Total Kafka messages processed",
    ["topic", "consumer_group", "status"],  # status: success, error, skipped
)

KAFKA_CONSUMER_LAG_MESSAGES = Gauge(
    "kafka_consumer_lag_messages",
    "Kafka consumer lag in messages",
    ["topic", "consumer_group"],
)

KAFKA_MESSAGE_PROCESSING_DURATION_MS = Histogram(
    "kafka_message_processing_duration_ms",
    "Time to process a single Kafka message in milliseconds",
    ["topic", "consumer_group"],
    buckets=(1.0, 5.0, 10.0, 50.0, 100.0, 500.0, 1000.0),
)

# Window State Metrics
WINDOW_STATE_POINTS = Gauge(
    "window_state_points_current",
    "Current number of points in rule window state",
    ["rule_id", "device_id"],
)

WINDOW_STATE_CLEANUP_DURATION_MS = Histogram(
    "window_state_cleanup_duration_ms",
    "Time to cleanup expired points from window state in milliseconds",
    ["rule_id"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0),
)

# Action Dispatch Metrics
ACTION_DISPATCH_DURATION_MS = Histogram(
    "action_dispatch_duration_ms",
    "Time to dispatch actions for an event in milliseconds",
    ["action_type"],  # action_type: notification, stop_machine
    buckets=(1.0, 5.0, 10.0, 50.0, 100.0, 500.0),
)

ACTIONS_DISPATCHED_TOTAL = Counter(
    "actions_dispatched_total",
    "Total actions dispatched",
    ["action_type", "status"],  # status: success, error
)

NOTIFICATION_DELIVERIES_ENQUEUED = Counter(
    "notification_deliveries_enqueued_total",
    "Total notification deliveries enqueued",
    ["template_id", "recipient_type"],  # recipient_type: email, sms
)

# Real-Time Evaluator Metrics
REALTIME_EVALUATOR_RULES_CACHED = Gauge(
    "realtime_evaluator_rules_cached",
    "Number of rules currently cached in evaluator",
    ["device_id"],
)

REALTIME_EVALUATOR_CACHE_HIT_RATE = Gauge(
    "realtime_evaluator_cache_hit_rate",
    "Cache hit rate for rule lookups (0-100%)",
    ["device_id"],
)

# Pipeline Latency Metrics
TELEMETRY_TO_EVENT_LATENCY_MS = Histogram(
    "telemetry_to_event_latency_ms",
    "End-to-end latency from telemetry ingestion to event creation in milliseconds",
    ["rule_id", "device_id"],
    buckets=(10.0, 50.0, 100.0, 500.0, 1000.0, 5000.0),
)

# Throughput Metrics
TELEMETRY_POINTS_PROCESSED_PER_SECOND = Gauge(
    "telemetry_points_per_second",
    "Telemetry points processed per second",
)

EVENTS_CREATED_PER_SECOND = Gauge(
    "events_created_per_second",
    "Events created per second",
)

# Queue Depth Metrics
KAFKA_EVENT_TOPIC_QUEUE_DEPTH = Gauge(
    "kafka_event_topic_queue_depth",
    "Depth of event.topic Kafka queue (approximate)",
)

RULES_CONSUMER_QUEUE_DEPTH = Gauge(
    "rules_consumer_queue_depth",
    "Approximate queue depth for rules consumer",
)

EVENTS_CONSUMER_QUEUE_DEPTH = Gauge(
    "events_consumer_queue_depth",
    "Approximate queue depth for events consumer",
)
