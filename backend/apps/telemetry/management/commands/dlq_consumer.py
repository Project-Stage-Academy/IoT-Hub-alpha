"""
DLQ Consumer - Monitors Dead Letter Queue and records metrics.

Reads messages from telemetry.dlq Kafka topic and records metrics
for Prometheus/Grafana monitoring.

Usage:
    python manage.py dlq_consumer
    python manage.py dlq_consumer --group-id custom-group
"""

import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from prometheus_client import start_http_server

from apps.rules.services.metrics import record_telemetry_dlq

logger = logging.getLogger("apps.telemetry.dlq_consumer")

try:
    from confluent_kafka import Consumer, KafkaError
except ImportError:
    Consumer, KafkaError = None, None


class Command(BaseCommand):
    """DLQ Consumer Django management command."""

    help = "DLQ Consumer: monitors telemetry.dlq and records metrics"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--group-id",
            type=str,
            default="dlq-consumer",
            help="Kafka consumer group ID (default: dlq-consumer)",
        )
        parser.add_argument(
            "--topic",
            type=str,
            default="telemetry.dlq",
            help="Kafka topic to consume (default: telemetry.dlq)",
        )
        parser.add_argument(
            "--bootstrap-servers",
            type=str,
            default="kafka:9092",
            help="Kafka bootstrap servers (default: kafka:9092)",
        )
        parser.add_argument(
            "--metrics-port",
            type=int,
            default=9104,
            help="Port to expose Prometheus metrics (default: 9104)",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Main consumer loop."""
        if Consumer is None:
            raise CommandError("confluent-kafka not installed.")

        group_id = options["group_id"]
        topic = options["topic"]
        bootstrap_servers = options["bootstrap_servers"]
        metrics_port = options["metrics_port"]

        # Start Prometheus metrics server
        if metrics_port:
            try:
                start_http_server(metrics_port)
                self.stdout.write(
                    self.style.SUCCESS(f"Metrics server started on port {metrics_port}")
                )
            except OSError as e:
                logger.warning(
                    "Could not start metrics server on port %s: %s",
                    metrics_port,
                    e,
                )

        self.stdout.write("Starting DLQ Consumer...")
        self.stdout.write(f"  Topic: {topic}")
        self.stdout.write(f"  Group ID: {group_id}")
        self.stdout.write(f"  Bootstrap servers: {bootstrap_servers}\n")

        consumer_config = {
            "bootstrap.servers": bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }

        try:
            consumer = Consumer(consumer_config)
            consumer.subscribe([topic])
            self.stdout.write("✓ Connected to Kafka\n")
        except Exception as e:
            raise CommandError(f"Failed to connect to Kafka: {e}") from e

        message_count = 0
        reason_counts = {}
        poll_timeout = 1.0

        try:
            self.stdout.write("Consuming messages...")
            self.stdout.write("(Press Ctrl+C to stop)\n")

            while True:
                message = consumer.poll(timeout=poll_timeout)

                if message is None:
                    continue

                if message.error():
                    if (
                        KafkaError
                        and message.error().code() == KafkaError._PARTITION_EOF
                    ):
                        continue
                    logger.error("Kafka error: %s", message.error())
                    continue

                try:
                    # Decode message value
                    value_bytes = message.value()
                    if value_bytes is None:
                        continue

                    message_data = json.loads(value_bytes.decode("utf-8"))

                    # Extract error reason from message
                    reason = message_data.get(
                        "error_reason",
                        message_data.get("error", {}).get("code", "unknown"),
                    )

                    # Get original topic (default: telemetry.raw)
                    original_topic = message_data.get("original_topic", "telemetry.raw")

                    # Record the metric
                    record_telemetry_dlq(topic=original_topic, reason=reason)
                    message_count += 1
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1

                    if message_count % 10 == 0:
                        self.stdout.write(f"✓ Processed {message_count} DLQ messages")

                except json.JSONDecodeError as e:
                    logger.error("Failed to parse message JSON: %s", e)
                    continue
                except Exception as e:  # noqa: BLE001
                    logger.error("Error processing message: %s", e)
                    continue

        except KeyboardInterrupt:
            self.stdout.write("\n\n⏸ Shutting down DLQ consumer...")
        finally:
            consumer.close()

            # Print summary
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write("DLQ Consumer Summary:")
            self.stdout.write(f"  Total messages processed: {message_count}")
            if reason_counts:
                self.stdout.write("  By error reason:")
                for reason, count in sorted(
                    reason_counts.items(), key=lambda x: x[1], reverse=True
                ):
                    self.stdout.write(f"    - {reason}: {count}")
            self.stdout.write(f"{'='*60}")
            self.stdout.write("\n✓ Metrics recorded in Prometheus")
            self.stdout.write("✓ Check Grafana dashboard for DLQ ratio")
