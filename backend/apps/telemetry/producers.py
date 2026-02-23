"""
Telemetry event producer abstraction.

Provides a pluggable interface for publishing raw telemetry events
to a message broker topic (e.g. Kafka ``telemetry.raw``).

Currently ships with a ``LogProducer`` stub that logs events.
When Kafka is available, implement ``KafkaProducer`` and set
``TELEMETRY_PRODUCER_BACKEND=kafka`` in Django settings.
"""

import logging
import threading
from typing import Any, Protocol, runtime_checkable

from django.conf import settings
from django.utils import timezone

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
    ) -> None:
        """
        Publish a raw telemetry payload to the ``telemetry.raw`` topic.

        Args:
            data: The raw JSON payload as received from the device.
            source: Ingestion channel identifier (``"http"`` or ``"mqtt"``).
            serial_number: Device serial number.
        """
        ...

    def close(self) -> None:
        """Release any resources held by the producer."""
        ...


class LogProducer:
    """
    Stub producer — logs events instead of publishing to a broker.

    Drop-in replacement for a real ``KafkaProducer``.  Every call to
    :meth:`publish_raw` writes a structured log entry so the pipeline
    can be verified end-to-end without Kafka infrastructure.
    """

    def publish_raw(
        self,
        data: dict[str, Any],
        source: str,
        serial_number: str,
    ) -> None:
        logger.info(
            "telemetry.raw event (log-only)",
            extra={
                "topic": TELEMETRY_RAW_TOPIC,
                "source": source,
                "serial_number": serial_number,
                "payload": data,
                "produced_at": timezone.now().isoformat(),
            },
        )

    def close(self) -> None:
        pass


# Singleton accessor
_producer_instance: TelemetryProducer | None = None
_producer_lock = threading.Lock()


def get_producer() -> TelemetryProducer:
    """
    Return the singleton :class:`TelemetryProducer` instance.

    Uses double-check locking for thread-safe initialisation.

    The concrete class is selected by ``settings.TELEMETRY_PRODUCER_BACKEND``:

    * ``"log"`` (default) — :class:`LogProducer`
    * ``"kafka"`` — reserved for the future :class:`KafkaProducer`
    """
    global _producer_instance
    if _producer_instance is None:
        with _producer_lock:
            if _producer_instance is None:  # Double-check locking
                backend = getattr(settings, "TELEMETRY_PRODUCER_BACKEND", "log")
                if backend == "kafka":
                    raise NotImplementedError(
                        "KafkaProducer is not yet implemented. "
                        "Set TELEMETRY_PRODUCER_BACKEND='log' or leave unset."
                    )
                _producer_instance = LogProducer()
                logger.info(
                    "Telemetry producer initialised",
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
) -> dict[str, Any]:
    """
    Wrap the raw device payload into the canonical ``telemetry.raw`` envelope.

    The envelope carries metadata (source, timestamp) alongside the
    original payload so downstream consumers can route and audit.

    .. note:: The payload is **not** deep-copied because it is serialised
       to JSON immediately downstream and never mutated after creation.
    """
    return {
        "source": source,
        "serial_number": serial_number,
        "received_at": timezone.now().isoformat(),
        "raw_payload": raw_payload,
    }
