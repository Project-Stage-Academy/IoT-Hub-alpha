"""
Event consumer for async processing of triggered rules.

Consumes events from Kafka topic, creates Event records, checks cooldown,
and dispatches actions (notifications, machine control, etc).

Usage:
    python manage.py events_consumer \\
        --input-topic events \\
        --group-id events-processor
"""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.events.services.event_handler import (
    event_handler,
    EventCooldownActive,
    external_event_handler,
)
from apps.events.services.actions import action_dispatch
from apps.events.services.helpers import handle_rules
from apps.rules.services.data_structure import EvalResults, ActionConfig
from apps.rules.services.metrics import track_kafka_message_processing
from apps.rules.models import Rule
from apps.events.services.external_events_data_structure import FakeRule

logger = logging.getLogger("apps.events.consumer")

try:
    from confluent_kafka import Consumer, KafkaError, Producer
except ImportError:  # pragma: no cover
    Consumer = None  # type: ignore[assignment]
    Producer = None  # type: ignore[assignment]
    KafkaError = None  # type: ignore[assignment]


class Command(BaseCommand):
    help = "Event consumer: process triggered rules and create events"

    def get_help(self):
        """Return help text with event processing pipeline description."""
        return """
Event Consumer - Async Event Processing Pipeline

Reads events from Kafka topic, creates Event records with cooldown protection,
and dispatches actions (notifications, machine control, etc).

Full Processing Pipeline:
  1. Subscribe to input Kafka topic (default: events)
  2. Parse event message JSON (rule_id, device_id, timestamp, message)
  3. Get Rule object from database
  4. Check cooldown: if active, skip (EventCooldownActive)
  5. Create Event record with telemetry snapshot
  6. Update rule.event_cooldown_until to prevent duplicate events
  7. Dispatch actions for each action in rule.action_config
  8. Commit consumer offset
  9. Continue to next message

Error Handling:
  - Invalid JSON: log error, skip message, commit offset
  - Missing rule: log error, skip message, commit offset
  - Cooldown active: log info, skip message, commit offset
  - Action dispatch failure: log error, continue with other actions
  - Kafka producer error: log error, retry on next poll()

Metrics Exported (Prometheus):
  - kafka_messages_processed_total: count by topic, consumer_group, status
  - kafka_message_processing_duration_ms: histogram of processing times
  - events_created_total: count by rule_id, device_id
  - actions_dispatched_total: count by action_type, status
"""

    def add_arguments(self, parser):
        parser.add_argument(
            "--input-topic",
            type=str,
            default=settings.KAFKA_TOPIC_EVENT,
            help=f"Input Kafka topic (default: {settings.KAFKA_TOPIC_EVENT})",
        )
        parser.add_argument(
            "--group-id",
            type=str,
            default="events-processor",
            help="Kafka consumer group ID (default: events-processor)",
        )
        parser.add_argument(
            "--metrics-port",
            type=int,
            default=9102,
            help="Port for Prometheus metrics HTTP server (default: 9102)",
        )

    def handle(self, **options):
        if Consumer is None or Producer is None:
            raise CommandError(
                "confluent-kafka dependency is not installed. "
                "Install requirements to use events_consumer."
            )

        input_topic = options["input_topic"]
        group_id = options["group_id"]
        metrics_port = options["metrics_port"]

        from prometheus_client import start_http_server

        try:
            start_http_server(metrics_port)
        except OSError as e:
            logger.warning(
                "Could not start Prometheus HTTP server on port %d: %s",
                metrics_port,
                str(e),
            )

        consumer = Consumer(self._build_consumer_config(group_id))
        consumer.subscribe([input_topic])

        self.stdout.write(
            self.style.SUCCESS(
                f"EventsConsumer started\n"
                f"   Input:  {input_topic}\n"
                f"   Group:  {group_id}\n"
                f"   Metrics: http://0.0.0.0:{metrics_port}/"
            )
        )

        stats = {
            "message_count": 0,
            "error_count": 0,
            "cooldown_skip_count": 0,
        }

        try:
            while True:
                msg = consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if self._handle_kafka_error(msg):
                    stats["error_count"] += 1
                    continue

                self._process_message(
                    msg=msg,
                    consumer=consumer,
                    input_topic=input_topic,
                    group_id=group_id,
                    stats=stats,
                )

        except KeyboardInterrupt:
            self.stdout.write("Shutting down EventsConsumer")
        finally:
            consumer.close()
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nFinal stats:\n"
                    f"   Messages:     {stats['message_count']}\n"
                    f"   Errors:       {stats['error_count']}\n"
                    f"   Cooldown:     {stats['cooldown_skip_count']}"
                )
            )

    def _process_message(
        self,
        *,
        msg,
        consumer,
        input_topic: str,
        group_id: str,
        stats: dict[str, int],
    ) -> None:
        try:
            with track_kafka_message_processing(input_topic, group_id):
                payload = json.loads(msg.value().decode("utf-8"))
                stats["message_count"] += 1

                rule_id, device_id, message_text, aggregate = self._parse_payload(
                    payload
                )
                if (
                    payload["type"] == "internal"
                    and isinstance(rule_id, UUID)
                    and isinstance(device_id, UUID)
                ):
                    rule = self._get_rule_or_none(rule_id=rule_id, device_id=device_id)
                    if rule is None:
                        consumer.commit(asynchronous=False)
                        return
                elif isinstance(rule_id, str):
                    rule = FakeRule(
                        id=rule_id,
                        action_config=payload["action_config"],
                        event_cooldown_until=payload["cooldown_min"],
                        additional_recipients=payload["external_recipients"],
                    )

                self._handle_event_actions(
                    rule_id=rule_id,
                    device_id=device_id,
                    message_text=message_text,
                    aggregate=aggregate,
                    rule=rule,
                    stats=stats,
                )

                self._print_progress(stats)
                consumer.commit(asynchronous=False)

        except (KeyError, ValueError, TypeError) as exc:
            logger.error(
                "Error parsing message: %s",
                str(exc),
                exc_info=True,
                extra={"raw_value": msg.value()},
            )
            stats["error_count"] += 1
            consumer.commit(asynchronous=False)
        except Exception as exc:
            logger.error(
                "Unexpected error: %s",
                str(exc),
                exc_info=True,
            )
            stats["error_count"] += 1
            consumer.commit(asynchronous=False)

    def _parse_payload(
        self,
        payload: dict[str, Any],
    ) -> tuple[UUID | str, UUID | str, str, EvalResults]:
        if payload["type"] == "internal":
            rule_id = UUID(payload["rule_id"])
            device_id = UUID(payload["device_id"])
        else:
            rule_id = str(payload["rule_id"])
            device_id = str(payload["device_id"])

        message_text = payload.get("message", "Rule triggered")
        snapshot = payload.get("telemetry_snapshot", {})
        aggregate = EvalResults(
            trigger=True,
            values=snapshot.get("values", []),
            start=(
                datetime.fromisoformat(snapshot["start"])
                if snapshot.get("start")
                else None
            ),
            end=(
                datetime.fromisoformat(snapshot["end"]) if snapshot.get("end") else None
            ),
        )
        return rule_id, device_id, message_text, aggregate

    def _get_rule_or_none(self, *, rule_id: UUID, device_id: UUID) -> Rule | None:
        try:
            return Rule.objects.get(id=rule_id)
        except Rule.DoesNotExist:
            logger.error(
                "Rule not found: %s",
                rule_id,
                extra={
                    "rule_id": str(rule_id),
                    "device_id": str(device_id),
                },
            )
            return None

    def _handle_event_actions(
        self,
        *,
        rule_id: UUID | str,
        device_id: UUID | str,
        message_text: str,
        aggregate: EvalResults,
        rule: Rule | FakeRule,
        stats: dict[str, int],
    ) -> None:
        try:
            if isinstance(rule, Rule):
                event = event_handler(aggregate, rule, message_text)
            else:
                event = external_event_handler(aggregate, rule.id, message_text, rule.event_cooldown_until)

            logger.info(
                "Event created: %s",
                event.id,
                extra={
                    "event_id": str(event.id),
                    "rule_id": str(rule_id),
                    "device_id": str(device_id),
                },
            )

            execution_results = self._dispatch_actions(
                rule_id=rule_id,
                rule=rule,
                aggregate=aggregate,
            )
            if execution_results:
                event.execution_results = execution_results
                event.save(update_fields=["execution_results"])

        except EventCooldownActive:
            logger.info(
                "Event in cooldown, skipping",
                extra={
                    "rule_id": str(rule_id),
                    "device_id": str(device_id),
                },
            )
            stats["cooldown_skip_count"] += 1

    def _dispatch_actions(
        self,
        *,
        rule_id: UUID | str,
        rule: Rule | FakeRule,
        aggregate: EvalResults,
    ) -> list[dict[str, Any]]:
        execution_results: list[dict[str, Any]] = []

        for action_config_dict in rule.action_config:
            try:
                action_config = ActionConfig.model_validate(action_config_dict)
            except Exception as exc:
                execution_results.append(
                    self._invalid_action_result(
                        action_config_dict=action_config_dict,
                        rule_id=rule_id,
                        error=exc,
                    )
                )
                continue

            execution_results.append(action_dispatch(action_config, rule, aggregate))

        return execution_results

    def _invalid_action_result(
        self,
        *,
        action_config_dict: Any,
        rule_id: UUID | str,
        error: Exception,
    ) -> dict[str, str]:
        invalid_action_type = (
            action_config_dict.get("type", "unknown")
            if isinstance(action_config_dict, dict)
            else "unknown"
        )
        logger.error(
            "Invalid action config",
            exc_info=True,
            extra={
                "rule_id": str(rule_id),
                "action_type": invalid_action_type,
            },
        )
        return {
            "type": invalid_action_type,
            "status": "failed",
            "error": f"Invalid action config: {error}",
            "completed_at": timezone.now().isoformat(),
        }

    def _print_progress(self, stats: dict[str, int]) -> None:
        if stats["message_count"] % 100 != 0:
            return
        self.stdout.write(
            f"Processed {stats['message_count']} messages "
            f"({stats['error_count']} errors, "
            f"{stats['cooldown_skip_count']} cooldown skips)"
        )

    def _build_consumer_config(self, group_id: str) -> dict:
        """
        Build Kafka consumer configuration from Django settings.

        Args:
            group_id: Kafka consumer group ID for this consumer instance.

        Returns:
            Dict containing complete confluent_kafka.Consumer configuration.
        """
        import os
        import socket

        config = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": (
                f"{settings.KAFKA_CLIENT_ID}-events-consumer-{group_id}-"
                f"{socket.gethostname()}-{os.getpid()}"
            ),
            "group.id": group_id,
            "security.protocol": settings.KAFKA_SECURITY_PROTOCOL,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }

        if settings.KAFKA_SASL_MECHANISM:
            config["sasl.mechanism"] = settings.KAFKA_SASL_MECHANISM
        if settings.KAFKA_SASL_USERNAME:
            config["sasl.username"] = settings.KAFKA_SASL_USERNAME
        if settings.KAFKA_SASL_PASSWORD:
            config["sasl.password"] = settings.KAFKA_SASL_PASSWORD

        return config

    def _handle_kafka_error(self, msg) -> bool:
        """
        Check if message contains Kafka error and log if fatal.

        Args:
            msg: confluent_kafka.Message object with potential error state.

        Returns:
            True if message contains fatal error (should be skipped),
            False otherwise.
        """
        if msg.error():
            if (
                KafkaError is not None
                and msg.error().code() == KafkaError._PARTITION_EOF
            ):
                return False

            logger.error(
                f"Kafka consumer error: {msg.error()}",
                extra={"error": str(msg.error())},
            )
            return True
        return False
