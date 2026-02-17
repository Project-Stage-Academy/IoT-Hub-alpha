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

        for message in messages:
            payload = json.dumps(message)
            try:
                self._producer.produce(target_topic, value=payload, headers=headers)
                self._producer.poll(0)
            except Exception as exc:
                raise KafkaPublishError(
                    f"Failed to enqueue Kafka message to '{target_topic}': {exc}"
                ) from exc

        timeout_seconds = max(settings.KAFKA_REQUEST_TIMEOUT_MS / 1000.0, 1.0)
        undelivered = self._producer.flush(timeout_seconds)
        if undelivered:
            raise KafkaDeliveryError(
                f"Failed to deliver {undelivered} Kafka message(s) to '{target_topic}'"
            )
