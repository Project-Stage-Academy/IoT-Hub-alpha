import json
import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Producer
except ImportError:  # pragma: no cover - depends on runtime environment
    Producer = None  # type: ignore[assignment]


class KafkaProducerError(Exception):
    """Base Kafka producer error."""


class KafkaPublishError(KafkaProducerError):
    """Raised when message enqueue fails."""


class KafkaDeliveryError(KafkaProducerError):
    """Raised when message delivery fails or times out."""


class TelemetryKafkaProducer:
    """Central Kafka producer wrapper for telemetry ingestion."""

    _producer: Producer | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._producer = self._get_or_create_producer()

    @classmethod
    def _get_or_create_producer(cls) -> Producer:
        if Producer is None:
            raise KafkaProducerError(
                "confluent-kafka dependency is not installed. "
                "Install requirements to use Kafka pipeline mode."
            )

        if cls._producer is not None:
            return cls._producer

        with cls._lock:
            if cls._producer is None:
                cls._producer = Producer(settings.KAFKA_PRODUCER_CONFIG)
                logger.info(
                    "Kafka producer initialized",
                    extra={
                        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                        "client_id": settings.KAFKA_CLIENT_ID,
                    },
                )

        return cls._producer

    @classmethod
    def reset_for_tests(cls) -> None:
        """Testing helper to reset singleton producer."""
        with cls._lock:
            cls._producer = None

    @staticmethod
    def resolve_topic(
        *,
        application: str = "telemetry",
        serial_number: str | None = None,
        requested_topic: str | None = None,
    ) -> str:
        """
        Resolve target topic using simple routing precedence:
        1) explicit topic override
        2) device prefix routing (if configured)
        3) application routing (if configured)
        4) telemetry raw default
        """
        if requested_topic:
            return requested_topic

        device_routes = getattr(settings, "KAFKA_DEVICE_TOPIC_ROUTES", {})
        if serial_number:
            device_key = serial_number.strip().upper()
            if device_key in device_routes:
                return device_routes[device_key]

            prefix = device_key.split("-", 1)[0]
            if prefix in device_routes:
                return device_routes[prefix]

        app_routes = getattr(
            settings,
            "KAFKA_APPLICATION_TOPIC_ROUTES",
            {"telemetry": settings.KAFKA_TOPIC_TELEMETRY_RAW},
        )
        return app_routes.get(application, settings.KAFKA_TOPIC_TELEMETRY_RAW)

    def publish_batch(
        self,
        messages: list[dict],
        topic: str | None = None,
        headers: list[tuple[str, bytes]] | None = None,
    ) -> None:
        target_topic = topic or settings.KAFKA_TOPIC_TELEMETRY_RAW
        delivery_errors: list[str] = []

        def _on_delivery(err, msg) -> None:
            if err is None:
                return

            topic_name = target_topic
            if msg is not None:
                topic_name = msg.topic()

            error_text = str(err)
            delivery_errors.append(f"{topic_name}: {error_text}")
            logger.error(
                "kafka.delivery_failed",
                extra={"error": error_text, "topic": topic_name},
            )

        for message in messages:
            payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
            key_raw = message.get("device_id") or message.get("serial_number")
            key = str(key_raw).encode("utf-8") if key_raw else None
            retries_left = 3

            while True:
                try:
                    self._producer.produce(
                        target_topic,
                        key=key,
                        value=payload,
                        headers=headers,
                        on_delivery=_on_delivery,
                    )
                    self._producer.poll(0)
                    break
                except BufferError as exc:
                    if retries_left == 0:
                        raise KafkaPublishError(
                            f"Kafka local queue is full for topic "
                            f"'{target_topic}': {exc}"
                        ) from exc

                    retries_left -= 1
                    self._producer.poll(0.1)
                except Exception as exc:
                    raise KafkaPublishError(
                        f"Failed to enqueue Kafka message to '{target_topic}': {exc}"
                    ) from exc

        timeout_seconds = max(settings.KAFKA_REQUEST_TIMEOUT_MS / 1000.0, 1.0)
        undelivered = self._producer.flush(timeout_seconds)
        if undelivered or delivery_errors:
            first_error = delivery_errors[0] if delivery_errors else "n/a"
            raise KafkaDeliveryError(
                f"Kafka delivery issues for topic '{target_topic}': "
                f"undelivered={undelivered}, callback_errors={len(delivery_errors)}, "
                f"first_error={first_error}"
            )
