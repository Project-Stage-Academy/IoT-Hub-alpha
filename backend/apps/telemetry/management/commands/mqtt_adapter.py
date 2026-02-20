"""
MQTT Adapter — subscribes to a Mosquitto broker and publishes raw
telemetry payloads to the ``telemetry.raw`` topic via the producer
abstraction.  Also handles device connection/disconnect events on
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

from django.conf import settings
from django.core.management.base import BaseCommand

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from apps.telemetry.producers import get_producer, build_raw_event

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


def handle_mqtt_message(topic: str, payload_bytes: bytes) -> dict:
    """
    Core MQTT ingestion function: parse and publish raw payload.

    Publishes the raw telemetry data to the ``telemetry.raw`` topic
    via the producer abstraction.  Validation and persistence are
    handled downstream by the Kafka consumer (separate story).

    Returns a dict with status information for logging/testing.
    """
    try:
        data = json.loads(payload_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning(
            "MQTT malformed JSON payload",
            extra={"topic": topic, "error": str(exc)},
        )
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
        return {
            "status": "error",
            "serial_number": None,
            "reason": "missing_serial_number",
            "detail": None,
        }

    data["serial_number"] = serial_number

    # Publish raw payload to telemetry.raw topic
    try:
        producer = get_producer()
        producer.publish_raw(
            data=build_raw_event(data, source="mqtt", serial_number=serial_number),
            source="mqtt",
            serial_number=serial_number,
        )
    except Exception as exc:
        logger.error(
            "MQTT failed to publish raw event",
            extra={"topic": topic, "error": str(exc)},
        )
        return {
            "status": "error",
            "serial_number": serial_number,
            "reason": "publish_failed",
            "detail": str(exc),
        }

    logger.info(
        "MQTT telemetry published to telemetry.raw",
        extra={"topic": topic, "serial_number": serial_number},
    )
    return {
        "status": "accepted",
        "serial_number": serial_number,
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

        self.stdout.write(f"Connecting to MQTT broker at {host}:{port}")
        self.stdout.write(f"Subscribing to topic: {topic} (QoS {qos})")

        client = mqtt.Client(CallbackAPIVersion.VERSION2)

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code == 0:
                self.stdout.write(self.style.SUCCESS("Connected to MQTT broker"))
                client.subscribe(topic, qos=qos)
                self.stdout.write(f"Subscribed to: {topic}")
                # Subscribe to device status topics for connect/disconnect events
                client.subscribe(DEVICE_STATUS_TOPIC, qos=1)
                self.stdout.write(f"Subscribed to: {DEVICE_STATUS_TOPIC}")
            else:
                self.stderr.write(self.style.ERROR(f"Connection failed: {reason_code}"))

        def on_message(client, userdata, msg):
            logger.debug(
                "MQTT message received",
                extra={"topic": msg.topic, "payload_size": len(msg.payload)},
            )
            # Route device status messages separately
            if msg.topic.endswith("/status") and msg.topic.startswith("devices/"):
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
