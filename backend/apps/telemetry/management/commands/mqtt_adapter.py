"""
MQTT Adapter — subscribes to a Mosquitto broker and publishes raw
telemetry payloads via the producer abstraction to a resolved Kafka
topic. Also handles device connection/disconnect events on
``devices/+/status``.

Usage:
    python manage.py mqtt_adapter
    python manage.py mqtt_adapter --topic "telemetry/#"
    python manage.py mqtt_adapter --host localhost --port 1883
"""

import json
import logging
import signal
import socket
import sys
import uuid
import hashlib
from typing import Any
import time

from prometheus_client import start_http_server

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from apps.telemetry.producers import get_producer, build_raw_event
from apps.telemetry.services import TelemetryBatchProcessor, TelemetryValidator
from config.metrics import (
    INGEST_ERRORS_TOTAL,
    INGEST_LATENCY_SECONDS,
    INGEST_MESSAGES_TOTAL,
)


logger = logging.getLogger(__name__)

DEVICE_STATUS_TOPIC = "devices/+/status"


def _extract_serial_number(topic: str) -> str | None:
    """
    Extract the device serial number from the MQTT topic.

    Expected topic format: telemetry/<serial_number>
    e.g. telemetry/TEMP-SN-002  ->  TEMP-SN-002
    """
    parts = topic.strip("/").split("/")
    if len(parts) >= 2:
        return parts[-1]
    return None


def _normalize_idempotency_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    if isinstance(value, (int, float, bool)):
        return str(value)
    return None


def _build_mqtt_idempotency_key(
    *,
    topic: str,
    serial_number: str,
    data: dict[str, Any],
    payload_bytes: bytes,
) -> str:
    explicit = _normalize_idempotency_value(data.get("idempotency_key"))
    if explicit:
        return explicit

    stable_fields: dict[str, str] = {}
    for field in ("message_id", "msg_id", "seq", "sequence", "timestamp", "ts"):
        normalized = _normalize_idempotency_value(data.get(field))
        if normalized:
            stable_fields[field] = normalized

    if stable_fields:
        base = json.dumps(
            {
                "serial_number": serial_number,
                "topic": topic,
                "fields": stable_fields,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
        return f"mqtt:{digest}"

    hasher = hashlib.sha256()
    hasher.update(serial_number.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(topic.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(payload_bytes)
    return f"mqtt:{hasher.hexdigest()}"


def handle_mqtt_message(topic: str, payload_bytes: bytes) -> dict:
    """
    Core MQTT ingestion function.

    Pipeline behavior is mode-dependent:
    * ``TELEMETRY_PIPELINE_MODE=kafka``: publish canonical raw event.
    * ``TELEMETRY_PIPELINE_MODE=direct``: validate and persist immediately.

    Returns a dict with status information for logging/testing.
    """
    started = time.perf_counter()

    def _record_error(reason: str, *, stage: str = "raw") -> None:
        INGEST_MESSAGES_TOTAL.labels(
            stage=stage,
            protocol="mqtt",
            status="failed",
        ).inc()
        INGEST_ERRORS_TOTAL.labels(
            component="mqtt_adapter",
            error_type=reason,
            protocol="mqtt",
        ).inc()

    try:
        data = json.loads(payload_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(
            "MQTT malformed JSON payload",
            extra={"topic": topic, "error": str(exc)},
        )
        _record_error("malformed_json", stage="raw")
        return {
            "status": "error",
            "serial_number": None,
            "reason": "malformed_json",
            "detail": str(exc),
        }

    if not isinstance(data, dict):
        logger.warning(
            "MQTT payload is not a JSON object",
            extra={"topic": topic},
        )
        _record_error("invalid_payload_type", stage="raw")
        return {
            "status": "error",
            "serial_number": None,
            "reason": "invalid_payload_type",
            "detail": None,
        }

    serial_number = data.get("serial_number") or _extract_serial_number(topic)
    if not serial_number:
        logger.warning(
            "MQTT message missing serial_number",
            extra={"topic": topic},
        )
        _record_error("missing_serial_number", stage="raw")
        return {
            "status": "error",
            "serial_number": None,
            "reason": "missing_serial_number",
            "detail": None,
        }

    data["serial_number"] = serial_number

    if settings.TELEMETRY_PIPELINE_MODE == "kafka":
        try:
            request_id = str(uuid.uuid4())
            received_at = timezone.now().isoformat()
            idempotency_key = _build_mqtt_idempotency_key(
                topic=topic,
                serial_number=serial_number,
                data=data,
                payload_bytes=payload_bytes,
            )
            producer = get_producer()
            published_topic = producer.publish_raw(
                data=build_raw_event(
                    data,
                    source="mqtt",
                    serial_number=serial_number,
                    request_id=request_id,
                    idempotency_key=idempotency_key,
                    ingest_index=0,
                    received_at=received_at,
                ),
                source="mqtt",
                serial_number=serial_number,
            )
        except Exception as exc:
            logger.error(
                "MQTT failed to publish raw event",
                extra={"topic": topic, "error": str(exc)},
            )
            _record_error("publish_failed", stage="raw")
            return {
                "status": "error",
                "serial_number": serial_number,
                "reason": "publish_failed",
                "detail": str(exc),
            }

        INGEST_MESSAGES_TOTAL.labels(
            stage="raw",
            protocol="mqtt",
            status="accepted",
        ).inc()
        INGEST_LATENCY_SECONDS.labels(
            stage="end_to_end",
            protocol="mqtt",
        ).observe(max(time.perf_counter() - started, 0.0))

        logger.info(
            "MQTT telemetry published to Kafka",
            extra={
                "source_topic": topic,
                "published_topic": published_topic,
                "serial_number": serial_number,
                "idempotency_key": idempotency_key,
            },
        )
        return {
            "status": "accepted",
            "serial_number": serial_number,
            "topic": published_topic,
            "idempotency_key": idempotency_key,
            "reason": None,
            "detail": None,
        }

    validated, error = TelemetryValidator.validate_single(data)
    if error:
        logger.warning(
            "MQTT message validation failed",
            extra={"topic": topic, "error": error},
        )
        _record_error("validation_failed", stage="raw")
        return {
            "status": "error",
            "serial_number": serial_number,
            "reason": "validation_failed",
            "detail": error,
        }
        
    INGEST_MESSAGES_TOTAL.labels(
        stage="raw",
        protocol="mqtt",
        status="accepted",
    ).inc()

    try:
        telemetry = TelemetryBatchProcessor.process_single(validated)
    except Exception as exc:
        logger.error(
            "MQTT failed to publish raw event",
            extra={"topic": topic, "error": str(exc)},
        )
        _record_error("persistence_failed", stage="db_write")
        return {
            "status": "error",
            "serial_number": serial_number,
            "reason": "persistence_failed",
            "detail": str(exc),
        }

    INGEST_MESSAGES_TOTAL.labels(
        stage="db_write",
        protocol="mqtt",
        status="accepted",
    ).inc()
    INGEST_LATENCY_SECONDS.labels(
        stage="end_to_end",
        protocol="mqtt",
    ).observe(max(time.perf_counter() - started, 0.0))

    logger.info(
        "MQTT telemetry ingested",
        extra={
            "topic": topic,
            "telemetry_id": telemetry.id,
            "device_id": str(telemetry.device_id),
        },
    )
    return {
        "status": "created",
        "serial_number": serial_number,
        "telemetry_id": telemetry.id,
        "device_id": str(telemetry.device_id),
        "reason": None,
        "detail": None,
    }


class Command(BaseCommand):
    help = (
        "Run a lightweight MQTT adapter that subscribes to a dev topic "
        "and routes messages into the telemetry ingestion pipeline."
    )

    # Device connection event handling

    @staticmethod
    def _handle_device_status(topic: str, payload_bytes: bytes) -> None:
        """
        Handle messages on ``devices/<serial>/status``.

        Devices are expected to:
        * publish ``online`` to their status topic on connect
        * set LWT (Last Will and Testament) to ``offline`` on the same topic
        """
        parts = topic.strip("/").split("/")
        if len(parts) < 2:
            return

        serial_number = parts[-2] if parts[-1] == "status" else parts[-1]
        try:
            status = payload_bytes.decode("utf-8", errors="replace").strip().lower()
        except Exception:
            status = "unknown"

        logger.info(
            "Device status change",
            extra={
                "serial_number": serial_number,
                "status": status,
                "topic": topic,
            },
        )

    def add_arguments(self, parser):
        parser.add_argument(
            "--host",
            type=str,
            default=settings.MQTT_BROKER_HOST,
            help=f"MQTT broker host (default: {settings.MQTT_BROKER_HOST})",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=settings.MQTT_BROKER_PORT,
            help=f"MQTT broker port (default: {settings.MQTT_BROKER_PORT})",
        )
        parser.add_argument(
            "--topic",
            type=str,
            default=settings.MQTT_TOPIC,
            help=f"MQTT topic to subscribe (default: {settings.MQTT_TOPIC})",
        )
        parser.add_argument(
            "--qos",
            type=int,
            default=settings.MQTT_QOS,
            help=f"MQTT QoS level (default: {settings.MQTT_QOS})",
        )

    def handle(self, *args, **options):
        host = options["host"]
        port = options["port"]
        topic = options["topic"]
        qos = options["qos"]

        # Expose Prometheus metrics for mqtt_adapter process
        try:
            start_http_server(9103)
            self.stdout.write("Metrics endpoint started on :9103")
        except OSError as exc:
            self.stderr.write(
                self.style.WARNING(f"Metrics endpoint :9103 not started: {exc}")
            )

        if settings.TELEMETRY_PIPELINE_MODE == "direct":
            try:
                connection.ensure_connection()
            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        "Cannot connect to database in direct pipeline mode: " f"{exc}"
                    )
                )
                sys.exit(1)

        self.stdout.write(f"Connecting to MQTT broker at {host}:{port}")
        self.stdout.write(f"Subscribing to topic: {topic} (QoS {qos})")

        client = mqtt.Client(CallbackAPIVersion.VERSION2)

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code == 0:
                self.stdout.write(self.style.SUCCESS("Connected to MQTT broker"))
                client.subscribe(topic, qos=qos)
                self.stdout.write(f"Subscribed to: {topic}")
                # Subscribe to device status topics for connect/disconnect events
                client.subscribe(DEVICE_STATUS_TOPIC, qos=qos)
                self.stdout.write(f"Subscribed to: {DEVICE_STATUS_TOPIC}")
            else:
                self.stderr.write(self.style.ERROR(f"Connection failed: {reason_code}"))

        def on_message(client, userdata, msg):
            logger.debug(
                "MQTT message received",
                extra={"topic": msg.topic, "payload_size": len(msg.payload)},
            )
            if msg.topic.startswith("devices/") and msg.topic.endswith("/status"):
                self._handle_device_status(msg.topic, msg.payload)
                return
            handle_mqtt_message(msg.topic, msg.payload)

        def on_disconnect(client, userdata, flags, reason_code, properties=None):
            if reason_code != 0:
                self.stderr.write(
                    self.style.WARNING(
                        f"Unexpected disconnect (rc={reason_code}), reconnecting..."
                    )
                )

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect

        # Graceful shutdown on SIGINT / SIGTERM
        def _shutdown(signum, frame):
            self.stdout.write("\nShutting down MQTT adapter...")
            client.loop_stop()
            client.disconnect()
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        try:
            socket.setdefaulttimeout(settings.MQTT_CONNECT_TIMEOUT)
            client.connect(host, port, keepalive=60)
            self.stdout.write("MQTT adapter running. Press Ctrl+C to stop.")
            client.loop_forever()
        except TimeoutError:
            self.stderr.write(
                self.style.ERROR(
                    f"Connection to MQTT broker at {host}:{port} "
                    f"timed out after {settings.MQTT_CONNECT_TIMEOUT}s"
                )
            )
            sys.exit(1)
        except ConnectionRefusedError:
            self.stderr.write(
                self.style.ERROR(f"Cannot connect to MQTT broker at {host}:{port}")
            )
            sys.exit(1)
        except OSError as exc:
            self.stderr.write(self.style.ERROR(f"MQTT connection error: {exc}"))
            sys.exit(1)
