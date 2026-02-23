"""
Telemetry event producer abstraction.

Provides a pluggable interface for publishing raw telemetry events
to a message broker topic (for example Kafka ``telemetry.raw``).
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from .kafka import KafkaProducerError, TelemetryKafkaProducer

logger = logging.getLogger(__name__)

TELEMETRY_RAW_TOPIC = "telemetry.raw"


@runtime_checkable
class TelemetryProducer(Protocol):
    """Structural interface every concrete producer must satisfy."""

    def publish_raw(
        self,
        data: dict[str, Any],
        source: str,
        serial_number: str,
    ) -> str:
        """
        Publish a raw telemetry payload to the raw topic.

        Args:
            data: Canonical telemetry.raw event envelope.
            source: Ingestion channel identifier (``"http"`` or ``"mqtt"``).
            serial_number: Device serial number.

        Returns:
            Resolved topic where the event was published.
        """
        ...

    def close(self) -> None:
        """Release any resources held by the producer."""
        ...

    def publish_raw_batch(
        self,
        data: list[dict[str, Any]],
        source: str,
        serial_number: str,
    ) -> str:
        """
        Publish multiple raw telemetry envelopes in a single producer operation.

        Args:
            data: Canonical telemetry.raw event envelopes.
            source: Ingestion channel identifier (``"http"`` or ``"mqtt"``).
            serial_number: Device serial number.

        Returns:
            Resolved topic where the batch was published.
        """
        ...


class LogProducer:
    """
    Stub producer that logs events instead of publishing to a broker.
    """

    def publish_raw(
        self,
        data: dict[str, Any],
        source: str,
        serial_number: str,
    ) -> str:
        self._assert_event_serial_matches(data, serial_number)
        topic = TelemetryKafkaProducer.resolve_topic(
            application="telemetry",
            serial_number=serial_number,
        )
        logger.info(
            "telemetry.raw event (log-only)",
            extra={
                "topic": topic,
                "source": source,
                "serial_number": serial_number,
                "idempotency_key": data.get("idempotency_key"),
                "payload": data,
                "produced_at": timezone.now().isoformat(),
            },
        )
        return topic

    def publish_raw_batch(
        self,
        data: list[dict[str, Any]],
        source: str,
        serial_number: str,
    ) -> str:
        self._assert_batch_serial_matches(data, serial_number)
        topic = TelemetryKafkaProducer.resolve_topic(
            application="telemetry",
            serial_number=serial_number,
        )
        for item in data:
            self.publish_raw(item, source=source, serial_number=serial_number)
        return topic

    @staticmethod
    def _assert_event_serial_matches(event: dict[str, Any], serial_number: str) -> None:
        event_serial = event.get("serial_number")
        if not isinstance(event_serial, str) or not event_serial.strip():
            raise ValueError("Raw event must contain non-empty serial_number")
        if event_serial != serial_number:
            raise ValueError(
                "Raw event serial_number mismatch: "
                f"event='{event_serial}', producer='{serial_number}'"
            )

    @classmethod
    def _assert_batch_serial_matches(
        cls,
        events: list[dict[str, Any]],
        serial_number: str,
    ) -> None:
        if not events:
            raise ValueError("Raw event batch must not be empty")
        for event in events:
            cls._assert_event_serial_matches(event, serial_number)

    def close(self) -> None:
        pass


class KafkaProducer:
    """Kafka-backed telemetry producer."""

    def __init__(self) -> None:
        self._kafka_producer = TelemetryKafkaProducer()

    def resolve_raw_topic(self, *, serial_number: str | None = None) -> str:
        return self._kafka_producer.resolve_topic(
            application="telemetry",
            serial_number=serial_number,
        )

    def publish_raw(
        self,
        data: dict[str, Any],
        source: str,
        serial_number: str,
    ) -> str:
        self._assert_event_serial_matches(data, serial_number)
        return self.publish_raw_batch(
            [data], source=source, serial_number=serial_number
        )

    def publish_raw_batch(
        self,
        data: list[dict[str, Any]],
        source: str,
        serial_number: str,
    ) -> str:
        self._assert_batch_serial_matches(data, serial_number)
        topic = self.resolve_raw_topic(serial_number=serial_number)
        headers: list[tuple[str, bytes]] = [("ingest_protocol", source.encode("utf-8"))]
        idempotency_key = self._extract_batch_idempotency_key(data)
        if idempotency_key:
            headers.append(("idempotency_key", idempotency_key.encode("utf-8")))

        self._kafka_producer.publish_batch(
            data,
            topic=topic,
            headers=headers,
        )
        return topic

    @staticmethod
    def _extract_batch_idempotency_key(events: list[dict[str, Any]]) -> str | None:
        keys: set[str] = set()
        for event in events:
            raw_key = event.get("idempotency_key")
            if isinstance(raw_key, str):
                key = raw_key.strip()
                if key:
                    keys.add(key)

        if len(keys) == 1:
            return next(iter(keys))

        if len(keys) > 1:
            logger.warning(
                "Kafka batch has mixed idempotency keys; header omitted",
                extra={"keys_count": len(keys)},
            )
        return None

    @staticmethod
    def _assert_event_serial_matches(event: dict[str, Any], serial_number: str) -> None:
        event_serial = event.get("serial_number")
        if not isinstance(event_serial, str) or not event_serial.strip():
            raise ValueError("Raw event must contain non-empty serial_number")
        if event_serial != serial_number:
            raise ValueError(
                "Raw event serial_number mismatch: "
                f"event='{event_serial}', producer='{serial_number}'"
            )

    @classmethod
    def _assert_batch_serial_matches(
        cls,
        events: list[dict[str, Any]],
        serial_number: str,
    ) -> None:
        if not events:
            raise ValueError("Raw event batch must not be empty")
        for event in events:
            cls._assert_event_serial_matches(event, serial_number)

    def close(self) -> None:
        self._kafka_producer.close()


_producer_instance: TelemetryProducer | None = None
_producer_lock = threading.Lock()


def get_producer() -> TelemetryProducer:
    """
    Return the singleton :class:`TelemetryProducer` instance.

    Uses double-check locking for thread-safe initialization.
    """
    global _producer_instance
    if _producer_instance is None:
        with _producer_lock:
            if _producer_instance is None:
                backend = (
                    str(getattr(settings, "TELEMETRY_PRODUCER_BACKEND", "log"))
                    .strip()
                    .lower()
                )
                if backend == "kafka":
                    try:
                        _producer_instance = KafkaProducer()
                    except KafkaProducerError:
                        logger.exception(
                            "Telemetry producer initialization failed",
                            extra={"backend": backend},
                        )
                        raise
                elif backend == "log":
                    _producer_instance = LogProducer()
                else:
                    raise ValueError(
                        "Invalid TELEMETRY_PRODUCER_BACKEND. "
                        "Allowed values: 'log', 'kafka'."
                    )

                logger.info(
                    "Telemetry producer initialized",
                    extra={"backend": backend},
                )
    return _producer_instance


def reset_producer() -> None:
    """Reset the singleton (useful for tests)."""
    global _producer_instance
    with _producer_lock:
        if _producer_instance is not None:
            _producer_instance.close()
        _producer_instance = None


def build_raw_event(
    raw_payload: dict[str, Any],
    source: str,
    serial_number: str,
    *,
    request_id: str | None = None,
    idempotency_key: str | None = None,
    ingest_index: int = 0,
    received_at: str | None = None,
) -> dict[str, Any]:
    """
    Wrap the raw payload into the canonical ``telemetry.raw`` envelope.
    """
    if isinstance(ingest_index, bool) or not isinstance(ingest_index, int):
        raise ValueError("ingest_index must be int")
    if ingest_index < 0:
        raise ValueError("ingest_index must be >= 0")

    event = {
        "request_id": request_id or str(uuid4()),
        "ingest_protocol": source,
        "serial_number": serial_number,
        "payload": raw_payload,
        "received_at": received_at or timezone.now().isoformat(),
        "ingest_index": ingest_index,
    }
    if isinstance(idempotency_key, str):
        key = idempotency_key.strip()
        if key:
            event["idempotency_key"] = key
    elif idempotency_key is not None:
        raise ValueError("idempotency_key must be str when provided")

    return event
