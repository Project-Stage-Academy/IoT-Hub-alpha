"""
MQTT Adapter - subscribes to a broker topic and forwards validated
messages into the same ingestion path used by the HTTP endpoint.

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

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from apps.telemetry.services import TelemetryValidator, TelemetryBatchProcessor

logger = logging.getLogger(__name__)


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


def handle_mqtt_message(topic: str, payload_bytes: bytes) -> dict:
    """
    Core ingestion function: parse, validate, persist.

    This is the same logical path as the HTTP POST view:
      TelemetryValidator.validate_single  ->  TelemetryBatchProcessor.process_single

    Returns a dict with status information for logging/testing.
    """
    connection.ensure_connection()

    try:
        data = json.loads(payload_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(
            "MQTT malformed JSON payload",
            extra={"topic": topic, "error": str(exc)},
        )
        return {"status": "error", "reason": "malformed_json", "detail": str(exc)}

    if not isinstance(data, dict):
        logger.warning(
            "MQTT payload is not a JSON object",
            extra={"topic": topic},
        )
        return {"status": "error", "reason": "invalid_payload_type"}

    serial_number = data.get("serial_number") or _extract_serial_number(topic)
    if not serial_number:
        logger.warning(
            "MQTT message missing serial_number",
            extra={"topic": topic},
        )
        return {"status": "error", "reason": "missing_serial_number"}

    data["serial_number"] = serial_number

    validated, error = TelemetryValidator.validate_single(data)
    if error:
        logger.warning(
            "MQTT message validation failed",
            extra={"topic": topic, "error": error},
        )
        return {"status": "error", "reason": "validation_failed", "detail": error}

    try:
        telemetry = TelemetryBatchProcessor.process_single(validated)
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
            "telemetry_id": telemetry.id,
            "device_id": str(telemetry.device_id),
        }
    except Exception as exc:
        logger.exception(
            "MQTT telemetry persistence failed",
            extra={"topic": topic, "error": str(exc)},
        )
        return {"status": "error", "reason": "persistence_failed", "detail": str(exc)}


class Command(BaseCommand):
    help = (
        "Run a lightweight MQTT adapter that subscribes to a dev topic "
        "and routes messages into the telemetry ingestion pipeline."
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

        self.stdout.write(f"Connecting to MQTT broker at {host}:{port}")
        self.stdout.write(f"Subscribing to topic: {topic} (QoS {qos})")

        client = mqtt.Client(CallbackAPIVersion.VERSION2)

        if settings.MQTT_USERNAME:
            client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        if settings.MQTT_USE_TLS:
            client.tls_set()

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code == 0:
                self.stdout.write(self.style.SUCCESS("Connected to MQTT broker"))
                client.subscribe(topic, qos=qos)
                self.stdout.write(f"Subscribed to: {topic}")
            else:
                self.stderr.write(self.style.ERROR(f"Connection failed: {reason_code}"))

        def on_message(client, userdata, msg):
            logger.debug(
                "MQTT message received",
                extra={"topic": msg.topic, "payload_size": len(msg.payload)},
            )
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
