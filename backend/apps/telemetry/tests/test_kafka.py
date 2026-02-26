import pytest
from unittest.mock import patch, MagicMock

from apps.telemetry import kafka as kafka_module
from apps.telemetry.kafka import (
    TelemetryKafkaProducer,
    KafkaProducerError,
    KafkaPublishError,
    KafkaDeliveryError,
)


class TestTelemetryKafkaProducer:

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


class _FakeMessage:
    def __init__(self, topic: str):
        self._topic = topic

    def topic(self) -> str:
        return self._topic


class _FakeProducer:
    def __init__(self, _config: dict | None = None):
        self.raise_on_produce = None
        self.delivery_error = None
        self.flush_result = 0
        self.produce_calls = []
        self.poll_calls = []
        self.flush_calls = []

    def produce(
        self,
        topic: str,
        *,
        key: bytes | None = None,
        value: bytes | None = None,
        headers: list[tuple[str, bytes]] | None = None,
        on_delivery=None,
    ) -> None:
        self.produce_calls.append(
            {
                "topic": topic,
                "key": key,
                "value": value,
                "headers": headers,
            }
        )
        if self.raise_on_produce is not None:
            raise self.raise_on_produce
        if on_delivery is not None:
            on_delivery(self.delivery_error, _FakeMessage(topic))

    def poll(self, timeout: float) -> None:
        self.poll_calls.append(timeout)

    def flush(self, timeout: float) -> int:
        self.flush_calls.append(timeout)
        return self.flush_result


@pytest.fixture(autouse=True)
def _reset_kafka_singleton():
    TelemetryKafkaProducer.reset_for_tests()
    yield
    TelemetryKafkaProducer.reset_for_tests()


class TestKafkaProducerBootstrap:
    def test_requires_confluent_dependency(self, monkeypatch):
        monkeypatch.setattr(kafka_module, "Producer", None)

        with pytest.raises(KafkaProducerError, match="dependency is not installed"):
            TelemetryKafkaProducer._get_or_create_producer()

    def test_initializes_singleton_once(self, monkeypatch, settings):
        created = []

        def _factory(config):
            producer = _FakeProducer(config)
            created.append((config, producer))
            return producer

        monkeypatch.setattr(kafka_module, "Producer", _factory)

        first = TelemetryKafkaProducer._get_or_create_producer()
        second = TelemetryKafkaProducer._get_or_create_producer()

        assert first is second
        assert len(created) == 1
        assert created[0][0] == settings.KAFKA_PRODUCER_CONFIG

    def test_reset_for_tests_flushes_and_clears_singleton(self):
        fake = _FakeProducer()
        TelemetryKafkaProducer._shared_producer = fake

        TelemetryKafkaProducer.reset_for_tests()

        assert TelemetryKafkaProducer._shared_producer is None
        assert fake.poll_calls == [0]
        assert fake.flush_calls == [1.0]


class TestTopicResolution:
    def test_requested_topic_override_wins(self):
        assert (
            TelemetryKafkaProducer.resolve_topic(requested_topic="telemetry.raw.custom")
            == "telemetry.raw.custom"
        )

    def test_device_exact_route(self, settings):
        settings.KAFKA_DEVICE_TOPIC_ROUTES = {"TEMP-SN-002": "telemetry.device"}

        topic = TelemetryKafkaProducer.resolve_topic(serial_number="temp-sn-002")

        assert topic == "telemetry.device"

    def test_device_prefix_route(self, settings):
        settings.KAFKA_DEVICE_TOPIC_ROUTES = {"TEMP": "telemetry.prefix"}

        topic = TelemetryKafkaProducer.resolve_topic(serial_number="temp-abc-1")

        assert topic == "telemetry.prefix"

    def test_application_route_fallback(self, settings):
        settings.KAFKA_DEVICE_TOPIC_ROUTES = {}
        settings.KAFKA_APPLICATION_TOPIC_ROUTES = {"events": "event.topic"}

        assert (
            TelemetryKafkaProducer.resolve_topic(application="events") == "event.topic"
        )
        assert (
            TelemetryKafkaProducer.resolve_topic(application="missing")
            == settings.KAFKA_TOPIC_TELEMETRY_RAW
        )


class TestPublishBatch:
    def _producer(self) -> TelemetryKafkaProducer:
        producer = TelemetryKafkaProducer.__new__(TelemetryKafkaProducer)
        producer._producer = _FakeProducer()
        return producer

    def test_retries_transient_errors(self, settings):
        settings.KAFKA_PUBLISH_MAX_RETRIES = 2
        producer = self._producer()

        with (
            patch.object(
                TelemetryKafkaProducer,
                "_publish_batch_once",
                side_effect=[KafkaPublishError("queue is full"), None],
            ) as mock_once,
            patch("apps.telemetry.kafka.time.sleep") as mock_sleep,
        ):
            producer.publish_batch(messages=[{"value": 1}], topic="telemetry.raw")

        assert mock_once.call_count == 2
        mock_sleep.assert_called_once()

    def test_non_transient_error_does_not_retry(self, settings):
        settings.KAFKA_PUBLISH_MAX_RETRIES = 3
        producer = self._producer()

        with (
            patch.object(
                TelemetryKafkaProducer,
                "_publish_batch_once",
                side_effect=KafkaPublishError("invalid payload"),
            ) as mock_once,
            patch("apps.telemetry.kafka.time.sleep") as mock_sleep,
        ):
            with pytest.raises(KafkaPublishError, match="invalid payload"):
                producer.publish_batch(messages=[{"value": 1}], topic="telemetry.raw")

        assert mock_once.call_count == 1
        mock_sleep.assert_not_called()

    def test_stops_after_max_retries(self, settings):
        settings.KAFKA_PUBLISH_MAX_RETRIES = 1
        producer = self._producer()

        with (
            patch.object(
                TelemetryKafkaProducer,
                "_publish_batch_once",
                side_effect=[
                    KafkaDeliveryError("timed out"),
                    KafkaDeliveryError("timed out"),
                ],
            ) as mock_once,
            patch("apps.telemetry.kafka.time.sleep") as mock_sleep,
        ):
            with pytest.raises(KafkaDeliveryError, match="timed out"):
                producer.publish_batch(messages=[{"value": 1}], topic="telemetry.raw")

        assert mock_once.call_count == 2
        mock_sleep.assert_called_once()


class TestPublishBatchOnce:
    def _producer_with_fake(self) -> tuple[TelemetryKafkaProducer, _FakeProducer]:
        fake = _FakeProducer()
        producer = TelemetryKafkaProducer.__new__(TelemetryKafkaProducer)
        producer._producer = fake
        return producer, fake

    def test_successful_batch_publish(self, settings):
        producer, fake = self._producer_with_fake()
        messages = [
            {"device_id": "dev-1", "value": 1},
            {"serial_number": "SN-2", "value": 2},
        ]

        producer._publish_batch_once(
            messages=messages,
            topic="telemetry.raw",
            headers=[("ingest_protocol", b"http")],
        )

        assert len(fake.produce_calls) == 2
        assert fake.produce_calls[0]["key"] == b"dev-1"
        assert fake.produce_calls[1]["key"] == b"SN-2"
        assert fake.flush_calls[-1] == max(
            (settings.KAFKA_REQUEST_TIMEOUT_MS / 1000.0)
            + TelemetryKafkaProducer._flush_timeout_buffer_seconds,
            1.0,
        )

    def test_delivery_callback_error_raises(self):
        producer, fake = self._producer_with_fake()
        fake.delivery_error = RuntimeError("broker down")

        with pytest.raises(KafkaDeliveryError, match="callback_errors=1"):
            producer._publish_batch_once(
                messages=[{"serial_number": "SN-1", "value": 1}],
                topic="telemetry.raw",
                headers=None,
            )

    def test_undelivered_flush_result_raises(self):
        producer, fake = self._producer_with_fake()
        fake.flush_result = 2

        with pytest.raises(KafkaDeliveryError, match="undelivered=2"):
            producer._publish_batch_once(
                messages=[{"serial_number": "SN-1", "value": 1}],
                topic="telemetry.raw",
                headers=None,
            )

    def test_buffer_error_becomes_publish_error(self):
        producer, fake = self._producer_with_fake()
        fake.raise_on_produce = BufferError("full")

        with pytest.raises(KafkaPublishError, match="local queue is full"):
            producer._publish_batch_once(
                messages=[{"serial_number": "SN-1", "value": 1}],
                topic="telemetry.raw",
                headers=None,
            )

        assert fake.poll_calls == [0.2]

    def test_generic_enqueue_error_becomes_publish_error(self):
        producer, fake = self._producer_with_fake()
        fake.raise_on_produce = RuntimeError("no route")

        with pytest.raises(KafkaPublishError, match="Failed to enqueue Kafka message"):
            producer._publish_batch_once(
                messages=[{"serial_number": "SN-1", "value": 1}],
                topic="telemetry.raw",
                headers=None,
            )


class TestUtilityMethods:
    def _producer(self, fake: _FakeProducer | None = None) -> TelemetryKafkaProducer:
        producer = TelemetryKafkaProducer.__new__(TelemetryKafkaProducer)
        producer._producer = fake or _FakeProducer()
        return producer

    def test_flush_timeout_minimum_is_one_second(self, settings):
        settings.KAFKA_REQUEST_TIMEOUT_MS = 250
        producer = self._producer()

        assert producer._flush_timeout_seconds() == 1.0

    def test_flush_timeout_adds_request_timeout_buffer(self, settings):
        settings.KAFKA_REQUEST_TIMEOUT_MS = 30_000
        producer = self._producer()
        expected = 30.0 + TelemetryKafkaProducer._flush_timeout_buffer_seconds

        assert producer._flush_timeout_seconds() == pytest.approx(expected)

    def test_close_respects_explicit_timeout_and_warns_undelivered(self, caplog):
        fake = _FakeProducer()
        fake.flush_result = 1
        producer = self._producer(fake=fake)

        with caplog.at_level("WARNING"):
            producer.close(timeout_seconds=-3)

        assert fake.flush_calls[-1] == 0.0
        assert "kafka.close_undelivered" in caplog.text

    @pytest.mark.parametrize(
        ("error_text", "expected"),
        [
            ("queue is full", True),
            ("request timed out", True),
            ("transport failure", True),
            ("validation failed", False),
        ],
    )
    def test_is_transient_error(self, error_text, expected):
        producer = self._producer()

        assert producer._is_transient_error(Exception(error_text)) is expected

    def test_backoff_without_jitter(self, settings):
        settings.KAFKA_RETRY_BACKOFF_BASE_MS = 100
        settings.KAFKA_RETRY_BACKOFF_MAX_MS = 2000
        settings.KAFKA_RETRY_BACKOFF_JITTER = 0.0
        producer = self._producer()

        assert producer._backoff_seconds(attempt=3) == pytest.approx(0.8)

    def test_backoff_with_jitter(self, settings):
        settings.KAFKA_RETRY_BACKOFF_BASE_MS = 100
        settings.KAFKA_RETRY_BACKOFF_MAX_MS = 2000
        settings.KAFKA_RETRY_BACKOFF_JITTER = 0.2
        producer = self._producer()

        with patch("apps.telemetry.kafka.random.uniform", return_value=10):
            assert producer._backoff_seconds(attempt=0) == pytest.approx(0.11)
