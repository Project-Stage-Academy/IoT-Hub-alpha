from unittest.mock import MagicMock, patch

import pytest

from apps.telemetry.producers import (
    KafkaProducer,
    LogProducer,
    TelemetryProducer,
    build_raw_event,
    get_producer,
    reset_producer,
)


class TestBuildRawEvent:
    def test_builds_task70_contract(self):
        payload = {"schema_version": "1.0", "value": 42}

        event = build_raw_event(
            payload,
            source="http",
            serial_number="TEMP-SN-002",
            request_id="req-1",
            ingest_index=3,
            received_at="2026-01-01T00:00:00+00:00",
        )

        assert event == {
            "request_id": "req-1",
            "ingest_protocol": "http",
            "serial_number": "TEMP-SN-002",
            "payload": payload,
            "received_at": "2026-01-01T00:00:00+00:00",
            "ingest_index": 3,
        }

    def test_includes_non_empty_idempotency_key(self):
        event = build_raw_event(
            {"value": 1},
            source="mqtt",
            serial_number="SN1",
            idempotency_key="  idem-1  ",
        )

        assert event["idempotency_key"] == "idem-1"

    @pytest.mark.parametrize("ingest_index", [-1, True, 1.2, "1"])
    def test_rejects_invalid_ingest_index(self, ingest_index):
        with pytest.raises(ValueError, match="ingest_index"):
            build_raw_event(
                {"value": 1},
                source="http",
                serial_number="SN1",
                ingest_index=ingest_index,
            )

    def test_rejects_invalid_idempotency_type(self):
        with pytest.raises(ValueError, match="idempotency_key"):
            build_raw_event(
                {"value": 1},
                source="http",
                serial_number="SN1",
                idempotency_key=123,  # type: ignore[arg-type]
            )


class TestLogProducer:
    def test_implements_protocol(self):
        assert isinstance(LogProducer(), TelemetryProducer)

    @patch("apps.telemetry.producers.TelemetryKafkaProducer.resolve_topic")
    def test_publish_returns_resolved_topic(self, mock_resolve_topic):
        mock_resolve_topic.return_value = "telemetry.raw.resolved"
        producer = LogProducer()

        topic = producer.publish_raw(
            data=build_raw_event(
                {"value": 42},
                source="http",
                serial_number="TEMP-SN-002",
            ),
            source="http",
            serial_number="TEMP-SN-002",
        )

        assert topic == "telemetry.raw.resolved"

    def test_publish_batch_rejects_mixed_serials(self):
        producer = LogProducer()
        events = [
            build_raw_event({"value": 1}, source="http", serial_number="SN-A"),
            build_raw_event({"value": 2}, source="http", serial_number="SN-B"),
        ]

        with pytest.raises(ValueError, match="serial_number mismatch"):
            producer.publish_raw_batch(events, source="http", serial_number="SN-A")


class TestKafkaProducer:
    @patch("apps.telemetry.producers.TelemetryKafkaProducer")
    def test_publish_batch_passes_headers_and_returns_topic(self, mock_impl_cls):
        mock_impl = mock_impl_cls.return_value
        mock_impl.resolve_topic.return_value = "telemetry.raw"

        producer = KafkaProducer()
        topic = producer.publish_raw_batch(
            data=[
                build_raw_event(
                    {"value": 1},
                    source="http",
                    serial_number="SN1",
                    idempotency_key="idem-1",
                ),
            ],
            source="http",
            serial_number="SN1",
        )

        assert topic == "telemetry.raw"
        mock_impl.publish_batch.assert_called_once()
        _, kwargs = mock_impl.publish_batch.call_args
        assert kwargs["topic"] == "telemetry.raw"
        assert ("ingest_protocol", b"http") in kwargs["headers"]
        assert ("idempotency_key", b"idem-1") in kwargs["headers"]


class TestGetProducer:
    def setup_method(self):
        reset_producer()

    def teardown_method(self):
        reset_producer()

    def test_default_returns_log(self, settings):
        settings.TELEMETRY_PRODUCER_BACKEND = "log"
        assert isinstance(get_producer(), LogProducer)

    @patch("apps.telemetry.producers.KafkaProducer")
    def test_kafka_backend_uses_kafka_producer(self, mock_kafka_cls, settings):
        settings.TELEMETRY_PRODUCER_BACKEND = "kafka"
        instance = MagicMock()
        mock_kafka_cls.return_value = instance

        producer = get_producer()

        assert producer is instance
        mock_kafka_cls.assert_called_once()

    def test_invalid_backend_raises(self, settings):
        settings.TELEMETRY_PRODUCER_BACKEND = "invalid"
        with pytest.raises(ValueError, match="Invalid TELEMETRY_PRODUCER_BACKEND"):
            get_producer()
