import asyncio
import json
import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Consumer, KafkaError
except ImportError:
    Consumer = None
    KafkaError = None

_consumer_task: asyncio.Task | None = None
_consumer_stop_event: threading.Event = threading.Event()


def _create_consumer() -> "Consumer":
    """Create Kafka consumer with settings from Django config."""
    if Consumer is None:
        raise RuntimeError(
            "confluent-kafka is not installed. " "Install it to use Kafka consumer."
        )

    config = {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "group.id": getattr(
            settings, "KAFKA_WEBSOCKET_CONSUMER_GROUP", "websocket-telemetry"
        ),
        "auto.offset.reset": "latest",
        "enable.auto.commit": True,
        "session.timeout.ms": 10000,
        "heartbeat.interval.ms": 3000,
    }

    if settings.KAFKA_SECURITY_PROTOCOL:
        config["security.protocol"] = settings.KAFKA_SECURITY_PROTOCOL
    if settings.KAFKA_SASL_MECHANISM:
        config["sasl.mechanism"] = settings.KAFKA_SASL_MECHANISM
    if settings.KAFKA_SASL_USERNAME:
        config["sasl.username"] = settings.KAFKA_SASL_USERNAME
    if settings.KAFKA_SASL_PASSWORD:
        config["sasl.password"] = settings.KAFKA_SASL_PASSWORD

    return Consumer(config)


async def _consumer_loop() -> None:
    """
    Consume messages from telemetry.raw and broadcast to WebSocket clients.
    Runs Kafka polling in a thread executor to avoid blocking the event loop.
    """
    from apps.telemetry.consumers import broadcast_telemetry, connected_clients

    topic = settings.KAFKA_TOPIC_TELEMETRY_RAW
    consumer = _create_consumer()
    consumer.subscribe([topic])

    logger.info(
        "telemetry_ws_consumer.started",
        extra={"topic": topic},
    )

    loop = asyncio.get_event_loop()
    _consumer_stop_event.clear()

    try:
        while not _consumer_stop_event.is_set():
            # Poll in thread to avoid blocking async event loop
            msg = await loop.run_in_executor(None, lambda: consumer.poll(timeout=1.0))

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error(
                    "telemetry_ws_consumer.error",
                    extra={"error": str(msg.error())},
                )
                continue

            # Parse and broadcast message
            try:
                value = msg.value()
                if value:
                    data = json.loads(value.decode("utf-8"))
                    data["type"] = "telemetry"

                    if connected_clients:
                        await broadcast_telemetry(data)

                        logger.debug(
                            "telemetry_ws_consumer.broadcast",
                            extra={
                                "serial_number": data.get("serial_number"),
                                "clients": len(connected_clients),
                            },
                        )
            except json.JSONDecodeError as e:
                logger.warning(
                    "telemetry_ws_consumer.invalid_json",
                    extra={
                        "error": str(e),
                        "raw": msg.value()[:100] if msg.value() else None,
                    },
                )
            except Exception as e:
                logger.error(
                    "telemetry_ws_consumer.broadcast_error",
                    extra={"error": str(e)},
                )

    except asyncio.CancelledError:
        logger.info("telemetry_ws_consumer.cancelled")
    finally:
        consumer.close()
        logger.info("telemetry_ws_consumer.stopped")


def start_telemetry_consumer() -> None:
    """Start the Kafka consumer background task."""
    global _consumer_task

    if Consumer is None:
        logger.warning(
            "telemetry_ws_consumer.skipped",
            extra={"reason": "confluent-kafka not installed"},
        )
        return

    if _consumer_task is not None and not _consumer_task.done():
        logger.debug("telemetry_ws_consumer.already_running")
        return

    _consumer_stop_event.clear()
    _consumer_task = asyncio.create_task(_consumer_loop())
    logger.info("telemetry_ws_consumer.task_started")


async def stop_telemetry_consumer() -> None:
    """Stop the Kafka consumer background task and wait for cleanup."""
    global _consumer_task

    _consumer_stop_event.set()

    if _consumer_task is not None and not _consumer_task.done():
        _consumer_task.cancel()
        try:
            await _consumer_task  # Wait for cleanup to complete
        except asyncio.CancelledError:
            pass  # Expected when task is cancelled
        _consumer_task = None
        logger.info("telemetry_ws_consumer.task_stopped")
