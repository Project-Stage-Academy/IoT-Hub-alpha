"""Metrics instrumentation for rule engine."""

import time
import logging
from contextlib import contextmanager
from typing import Optional
from uuid import UUID

from config.metrics import (
    RULE_EVALUATION_DURATION_MS,
    RULES_EVALUATED_TOTAL,
    RULES_TRIGGERED_TOTAL,
    RULE_EVALUATION_ERRORS,
    EVENTS_CREATED_TOTAL,
    EVENTS_COOLDOWN_SKIPPED,
    EVENT_CREATION_DURATION_MS,
    KAFKA_MESSAGES_PROCESSED,
    KAFKA_MESSAGE_PROCESSING_DURATION_MS,
    WINDOW_STATE_POINTS,
    WINDOW_STATE_CLEANUP_DURATION_MS,
    ACTION_DISPATCH_DURATION_MS,
    ACTIONS_DISPATCHED_TOTAL,
    NOTIFICATION_DELIVERIES_ENQUEUED,
    REALTIME_EVALUATOR_RULES_CACHED,
    REALTIME_EVALUATOR_CACHE_HIT_RATE,
    TELEMETRY_TO_EVENT_LATENCY_MS,
    TELEMETRY_POINTS_PROCESSED_PER_SECOND,
    EVENTS_CREATED_PER_SECOND,
)

logger = logging.getLogger("apps.rules.metrics")


@contextmanager
def track_rule_evaluation(rule_id: UUID, device_id: UUID, operator: str):
    """
    Track rule evaluation timing and errors.

    Result tracking (triggered/skipped) is done separately via
    record_rule_result() after checking the eval result.

    Usage:
        with track_rule_evaluation(rule_id, device_id, "gt"):
            result = eval_rule(...)
        record_rule_result(rule_id, device_id, result.trigger)
    """
    start_time = time.time()

    try:
        yield
    except Exception as e:
        logger.error(f"Rule evaluation error: {e}")
        RULES_EVALUATED_TOTAL.labels(
            rule_id=str(rule_id),
            device_id=str(device_id),
            result="error",
        ).inc()
        RULE_EVALUATION_ERRORS.labels(
            rule_id=str(rule_id),
            error_type=type(e).__name__,
        ).inc()
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        RULE_EVALUATION_DURATION_MS.labels(
            rule_id=str(rule_id),
            device_id=str(device_id),
            operator=operator,
        ).observe(duration_ms)


def record_rule_result(rule_id: UUID, device_id: UUID, triggered: bool):
    """Record whether a rule evaluation resulted in trigger or skip."""
    result = "triggered" if triggered else "skipped"
    RULES_EVALUATED_TOTAL.labels(
        rule_id=str(rule_id),
        device_id=str(device_id),
        result=result,
    ).inc()

    if triggered:
        RULES_TRIGGERED_TOTAL.labels(
            rule_id=str(rule_id),
            device_id=str(device_id),
        ).inc()


@contextmanager
def track_event_creation(rule_id: UUID, device_id: Optional[UUID] = None):
    """
    Track Event model creation timing and increment creation counter.

    Context manager for measuring time to create Event record. Records both
    latency histogram and increment counter labeled by rule and device.

    Usage:
        with track_event_creation(rule_id, device_id):
            event = Event.objects.create(...)

    Args:
        rule_id: Rule that triggered event creation
        device_id: Device that triggered rule (optional, defaults to "unknown" for label)

    Metrics Updated:
        - event_creation_duration_ms: histogram of creation times
        - events_created_total: incremented by 1
    """
    start_time = time.time()

    try:
        yield
        EVENTS_CREATED_TOTAL.labels(
            rule_id=str(rule_id),
            device_id=str(device_id) if device_id else "unknown",
        ).inc()
    finally:
        duration_ms = (time.time() - start_time) * 1000
        EVENT_CREATION_DURATION_MS.labels(
            rule_id=str(rule_id),
        ).observe(duration_ms)


@contextmanager
def track_kafka_message_processing(topic: str, consumer_group: str):
    """
    Track Kafka message processing latency and status (success/error).

    Context manager for measuring end-to-end time to process single Kafka message.
    Records status as 'success' if no exception, 'error' if exception raised.
    Always records timing regardless of success/failure.

    Usage:
        with track_kafka_message_processing(topic, group):
            payload = json.loads(msg.value().decode("utf-8"))
            process_message(payload)
        # Timing and status recorded here

    Args:
        topic: Kafka topic being consumed (used for metric labels)
        consumer_group: Consumer group ID (used for metric labels)

    Metrics Updated:
        - kafka_message_processing_duration_ms: histogram of processing times
        - kafka_messages_processed_total: incremented by 1 with status label

    Raises:
        Re-raises any exception from wrapped code after recording error status
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception as e:
        logger.error(f"Kafka processing error: {e}")
        status = "error"
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        KAFKA_MESSAGE_PROCESSING_DURATION_MS.labels(
            topic=topic,
            consumer_group=consumer_group,
        ).observe(duration_ms)

        KAFKA_MESSAGES_PROCESSED.labels(
            topic=topic,
            consumer_group=consumer_group,
            status=status,
        ).inc()


@contextmanager
def track_action_dispatch(action_type: str):
    """
    Track action dispatch latency and status (success/error).

    Context manager for measuring time to dispatch action (notification, stop_machine, etc.).
    Records status as 'success' if no exception, 'error' if exception raised.
    Always records timing regardless of success/failure.

    Usage:
        with track_action_dispatch("notification"):
            dispatch_msg(action_config, rule, aggregate)
        # Timing and status recorded here

    Args:
        action_type: Type of action being dispatched (e.g., "notification", "stop_machine")
                     Used for metric labels to distinguish different action types

    Metrics Updated:
        - action_dispatch_duration_ms: histogram of dispatch times by action_type
        - actions_dispatched_total: incremented by 1 with action_type and status labels

    Raises:
        Re-raises any exception from wrapped code after recording error status
    """
    start_time = time.time()
    status = "success"

    try:
        yield
    except Exception as e:
        logger.error(f"Action dispatch error: {e}")
        status = "error"
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        ACTION_DISPATCH_DURATION_MS.labels(
            action_type=action_type,
        ).observe(duration_ms)

        ACTIONS_DISPATCHED_TOTAL.labels(
            action_type=action_type,
            status=status,
        ).inc()


def record_cooldown_skipped(rule_id: UUID, device_id: UUID):
    """Record when an event is skipped due to cooldown."""
    EVENTS_COOLDOWN_SKIPPED.labels(
        rule_id=str(rule_id),
        device_id=str(device_id),
    ).inc()


def record_window_state_points(rule_id: UUID, device_id: UUID, point_count: int):
    """Update current window state point count."""
    WINDOW_STATE_POINTS.labels(
        rule_id=str(rule_id),
        device_id=str(device_id),
    ).set(point_count)


@contextmanager
def track_window_state_cleanup(rule_id: UUID):
    """Track window state cleanup time."""
    start_time = time.time()

    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        WINDOW_STATE_CLEANUP_DURATION_MS.labels(
            rule_id=str(rule_id),
        ).observe(duration_ms)


def record_notification_enqueued(template_id: int, recipient_type: str):
    """Record a notification delivery enqueued."""
    NOTIFICATION_DELIVERIES_ENQUEUED.labels(
        template_id=str(template_id),
        recipient_type=recipient_type,
    ).inc()


def record_evaluator_cache_stats(device_id: UUID, cached_rules: int, hit_rate: float):
    """
    Record evaluator cache statistics.

    Args:
        device_id: Device UUID
        cached_rules: Number of rules cached
        hit_rate: Cache hit rate as percentage (0-100)
    """
    REALTIME_EVALUATOR_RULES_CACHED.labels(
        device_id=str(device_id),
    ).set(cached_rules)

    REALTIME_EVALUATOR_CACHE_HIT_RATE.labels(
        device_id=str(device_id),
    ).set(hit_rate)


def record_telemetry_to_event_latency(
    rule_id: UUID,
    device_id: UUID,
    latency_ms: float,
):
    """Record end-to-end latency from telemetry to event creation."""
    TELEMETRY_TO_EVENT_LATENCY_MS.labels(
        rule_id=str(rule_id),
        device_id=str(device_id),
    ).observe(latency_ms)


def update_throughput_metrics(
    telemetry_per_second: float,
    events_per_second: float,
):
    """
    Update system throughput gauges (telemetry and event creation rates).

    Sets current system throughput metrics based on real-time measurements.
    Should be called periodically (e.g., every 10-30 seconds) to track pipeline
    throughput and detect bottlenecks.

    Usage:
        # In background task or monitoring thread
        telemetry_rate = telemetry_count / elapsed_seconds
        event_rate = event_count / elapsed_seconds
        update_throughput_metrics(telemetry_rate, event_rate)

    Args:
        telemetry_per_second: Telemetry points processed per second
        events_per_second: Events created per second

    Metrics Updated:
        - telemetry_points_per_second: gauge set to telemetry_per_second
        - events_created_per_second: gauge set to events_per_second
    """
    TELEMETRY_POINTS_PROCESSED_PER_SECOND.set(telemetry_per_second)
    EVENTS_CREATED_PER_SECOND.set(events_per_second)
