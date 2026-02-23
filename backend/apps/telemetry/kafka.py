from __future__ import annotations

import json
import logging
import random
import threading
import time
from typing import ClassVar

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

    _shared_producer: ClassVar[Producer | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _publish_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._producer: Producer = self._get_or_create_producer()

    @classmethod
    def _get_or_create_producer(cls) -> Producer:
        if Producer is None:
            raise KafkaProducerError(
                "confluent-kafka dependency is not installed. "
                "Install requirements to use Kafka pipeline mode."
            )

        if cls._shared_producer is not None:
            return cls._shared_producer

        with cls._lock:
            if cls._shared_producer is None:
                cls._shared_producer = Producer(settings.KAFKA_PRODUCER_CONFIG)
                logger.info(
                    "Kafka producer initialized",
                    extra={
                        "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
                        "client_id": settings.KAFKA_CLIENT_ID,
                    },
                )

        # Guard for static type checkers.
        assert cls._shared_producer is not None
        return cls._shared_producer

    @classmethod
    def reset_for_tests(cls) -> None:
        """Testing helper to reset singleton producer."""
        producer_to_close: Producer | None = None
        with cls._lock:
            producer_to_close = cls._shared_producer
            cls._shared_producer = None

        if producer_to_close is None:
            return

        try:
            with cls._publish_lock:
                producer_to_close.poll(0)
                producer_to_close.flush(1.0)
        except Exception as exc:  # pragma: no cover - best effort cleanup
            logger.warning(
                "Kafka producer reset flush failed",
                extra={"error": str(exc)},
            )

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
        max_retries = settings.KAFKA_PUBLISH_MAX_RETRIES
        attempt = 0

        while True:
            try:
                self._publish_batch_once(
                    messages=messages,
                    topic=target_topic,
                    headers=headers,
                )
                return
            except (KafkaPublishError, KafkaDeliveryError) as exc:
                if attempt >= max_retries or not self._is_transient_error(exc):
                    raise

                sleep_seconds = self._backoff_seconds(attempt)
                logger.warning(
                    "kafka.publish_retrying",
                    extra={
                        "topic": target_topic,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "sleep_seconds": round(sleep_seconds, 3),
                        "error": str(exc),
                    },
                )
                time.sleep(sleep_seconds)
                attempt += 1

    def _publish_batch_once(
        self,
        *,
        messages: list[dict],
        topic: str,
        headers: list[tuple[str, bytes]] | None,
    ) -> None:
        error_lock = threading.Lock()
        error_count = 0
        first_error: str | None = None

        def _on_delivery(err, msg) -> None:
            nonlocal error_count, first_error
            if err is None:
                return

            topic_name = topic
            if msg is not None:
                topic_name = msg.topic()

            error_text = str(err)
            logger.error(
                "kafka.delivery_failed",
                extra={"error": error_text, "topic": topic_name},
            )
            with error_lock:
                error_count += 1
                if first_error is None:
                    first_error = f"{topic_name}: {error_text}"

        def _produce_once(*, payload: bytes, key: bytes | None) -> None:
            self._producer.produce(
                topic,
                key=key,
                value=payload,
                headers=headers,
                on_delivery=_on_delivery,
            )
            self._producer.poll(0)

        with self.__class__._publish_lock:
            for message in messages:
                payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
                key_raw = message.get("device_id") or message.get("serial_number")
                key = str(key_raw).encode("utf-8") if key_raw else None

                try:
                    _produce_once(payload=payload, key=key)
                except BufferError as exc:
                    # Let producer drain once, then escalate to outer retry loop.
                    self._producer.poll(0.2)
                    raise KafkaPublishError(
                        f"Kafka local queue is full for topic '{topic}': {exc}"
                    ) from exc
                except Exception as exc:
                    raise KafkaPublishError(
                        f"Failed to enqueue Kafka message to '{topic}': {exc}"
                    ) from exc

            timeout_seconds = self._flush_timeout_seconds()
            undelivered = self._producer.flush(timeout_seconds)

        with error_lock:
            callback_errors = error_count
            first_callback_error = first_error or "n/a"

        if undelivered or callback_errors:
            raise KafkaDeliveryError(
                f"Kafka delivery issues for topic '{topic}': "
                f"undelivered={undelivered}, callback_errors={callback_errors}, "
                f"first_error={first_callback_error}"
            )

    def _flush_timeout_seconds(self) -> float:
        return max(settings.KAFKA_REQUEST_TIMEOUT_MS / 1000.0, 1.0)

    def close(self, timeout_seconds: float | None = None) -> None:
        timeout = (
            self._flush_timeout_seconds()
            if timeout_seconds is None
            else max(timeout_seconds, 0.0)
        )
        with self.__class__._publish_lock:
            self._producer.poll(0)
            undelivered = self._producer.flush(timeout)

        if undelivered:
            logger.warning(
                "kafka.close_undelivered",
                extra={"undelivered": undelivered, "timeout_seconds": timeout},
            )

    def _is_transient_error(self, exc: Exception) -> bool:
        lowered = str(exc).lower()
        markers = (
            "queue is full",
            "timed out",
            "timeout",
            "transport",
            "all brokers down",
            "connection",
            "temporarily unavailable",
            "leader not available",
            "not enough replicas",
        )
        return any(marker in lowered for marker in markers)

    def _backoff_seconds(self, attempt: int) -> float:
        base_ms = settings.KAFKA_RETRY_BACKOFF_BASE_MS
        max_ms = settings.KAFKA_RETRY_BACKOFF_MAX_MS
        jitter = settings.KAFKA_RETRY_BACKOFF_JITTER

        delay_ms = min(base_ms * (2**attempt), max_ms)
        if jitter > 0:
            jitter_delta = delay_ms * jitter
            delay_ms += random.uniform(-jitter_delta, jitter_delta)

        return max(delay_ms / 1000.0, 0.0)
