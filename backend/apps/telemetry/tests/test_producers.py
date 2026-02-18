import pytest
from unittest.mock import patch

from apps.telemetry.producers import (
    LogProducer,
    TelemetryProducer,
    build_raw_event,
    get_producer,
    reset_producer,
    TELEMETRY_RAW_TOPIC,
)


class TestLogProducer:
    """Unit tests for the LogProducer stub."""

    def test_implements_protocol(self):
        assert isinstance(LogProducer(), TelemetryProducer)

    def test_publish_raw_logs_event(self, caplog):
        producer = LogProducer()

        with caplog.at_level("INFO"):
            producer.publish_raw(
                data={"raw_payload": {"value": 42}},
                source="http",
                serial_number="TEMP-SN-002",
            )

        assert "telemetry.raw event" in caplog.text

    def test_close_is_noop(self):
        producer = LogProducer()
        producer.close()  # should not raise


class TestBuildRawEvent:
    """Unit tests for the raw event envelope builder."""

    def test_envelope_structure(self):
        raw = {"schema_version": "1.0", "value": 2550, "serial_number": "TEMP-SN-002"}

        event = build_raw_event(raw, source="http", serial_number="TEMP-SN-002")

        assert event["source"] == "http"
        assert event["serial_number"] == "TEMP-SN-002"
        assert "received_at" in event
        assert event["raw_payload"] == raw

    def test_deep_copies_payload(self):
        raw = {"nested": {"key": "original"}}

        event = build_raw_event(raw, source="mqtt", serial_number="SN1")

        # Mutate the original — event must be unaffected
        raw["nested"]["key"] = "mutated"
        assert event["raw_payload"]["nested"]["key"] == "original"

    def test_source_values(self):
        raw = {"value": 1}

        http_event = build_raw_event(raw, source="http", serial_number="SN1")
        mqtt_event = build_raw_event(raw, source="mqtt", serial_number="SN1")

        assert http_event["source"] == "http"
        assert mqtt_event["source"] == "mqtt"


class TestGetProducer:
    """Unit tests for the singleton producer factory."""

    def setup_method(self):
        reset_producer()

    def teardown_method(self):
        reset_producer()

    def test_returns_log_producer_by_default(self, settings):
        settings.TELEMETRY_PRODUCER_BACKEND = "log"
        producer = get_producer()
        assert isinstance(producer, LogProducer)

    def test_singleton_returns_same_instance(self, settings):
        settings.TELEMETRY_PRODUCER_BACKEND = "log"
        p1 = get_producer()
        p2 = get_producer()
        assert p1 is p2

    def test_kafka_backend_raises_not_implemented(self, settings):
        settings.TELEMETRY_PRODUCER_BACKEND = "kafka"
        with pytest.raises(NotImplementedError, match="KafkaProducer"):
            get_producer()

    def test_reset_allows_reconfiguration(self, settings):
        settings.TELEMETRY_PRODUCER_BACKEND = "log"
        p1 = get_producer()
        reset_producer()
        p2 = get_producer()
        assert p1 is not p2
