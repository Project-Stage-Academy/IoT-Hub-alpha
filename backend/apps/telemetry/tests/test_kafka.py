import pytest
from unittest.mock import patch, MagicMock

from apps.telemetry.kafka import (
    TelemetryKafkaProducer,
    KafkaProducerError,
    KafkaPublishError,
    KafkaDeliveryError,
)


class TestTelemetryKafkaProducer:

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        TelemetryKafkaProducer.reset_for_tests()

    @patch("apps.telemetry.kafka.Producer")
    def test_singleton_pattern(self, mock_producer_class):
        mock_producer_class.return_value = MagicMock()

        producer1 = TelemetryKafkaProducer()
        producer2 = TelemetryKafkaProducer()

        assert producer1._producer is producer2._producer
        mock_producer_class.assert_called_once()

    @patch("apps.telemetry.kafka.Producer", new=None)
    def test_missing_dependency(self):
        with pytest.raises(
            KafkaProducerError, match="confluent-kafka dependency is not installed"
        ):
            TelemetryKafkaProducer()

    def test_resolve_topic_explicit(self):
        assert (
            TelemetryKafkaProducer.resolve_topic(requested_topic="my.custom.topic")
            == "my.custom.topic"
        )

    def test_resolve_topic_routing(self, settings):
        settings.KAFKA_DEVICE_TOPIC_ROUTES = {
            "SN-123": "topic.special",
            "PREFIX": "topic.prefix",
        }
        settings.KAFKA_TOPIC_TELEMETRY_RAW = "topic.default"

        assert (
            TelemetryKafkaProducer.resolve_topic(serial_number="SN-123")
            == "topic.special"
        )
        assert (
            TelemetryKafkaProducer.resolve_topic(serial_number="PREFIX-999")
            == "topic.prefix"
        )
        assert (
            TelemetryKafkaProducer.resolve_topic(serial_number="UNKNOWN-000")
            == "topic.default"
        )

    @patch("apps.telemetry.kafka.Producer")
    def test_publish_batch_success(self, mock_producer_class):
        mock_instance = MagicMock()
        mock_instance.flush.return_value = 0
        mock_producer_class.return_value = mock_instance

        producer = TelemetryKafkaProducer()
        producer.publish_batch([{"serial_number": "SN-1", "val": 1}])

        mock_instance.produce.assert_called_once()
        mock_instance.poll.assert_called()
        mock_instance.flush.assert_called_once()

    @patch("apps.telemetry.kafka.Producer")
    def test_publish_batch_buffer_error(self, mock_producer_class):
        mock_instance = MagicMock()
        mock_instance.produce.side_effect = BufferError("Local queue full")
        mock_producer_class.return_value = mock_instance

        producer = TelemetryKafkaProducer()

        with pytest.raises(KafkaPublishError, match="Kafka local queue is full"):
            producer.publish_batch([{"val": 1}])

        assert mock_instance.produce.call_count == 4

    @patch("apps.telemetry.kafka.Producer")
    def test_publish_batch_delivery_error(self, mock_producer_class):
        mock_instance = MagicMock()
        mock_instance.flush.return_value = 2
        mock_producer_class.return_value = mock_instance

        producer = TelemetryKafkaProducer()

        with pytest.raises(KafkaDeliveryError, match="undelivered=2"):
            producer.publish_batch([{"val": 1}, {"val": 2}])
