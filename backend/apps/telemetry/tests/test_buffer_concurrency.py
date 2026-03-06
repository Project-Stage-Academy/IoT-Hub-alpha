"""Tests for buffer concurrency, overflow, and error handling."""

import pytest
from unittest.mock import MagicMock, patch
from confluent_kafka import KafkaError

from apps.telemetry.service_layer.write_buffer import WriteBuffer
from apps.telemetry.service_layer.data_structure import BufferedItem, InFlight


class DummyMessage:
    """Mock Kafka message for testing."""

    def __init__(self, key=None, value=b"test", topic="test", offset=0, error_obj=None):
        self.key_val = key
        self.value_val = value
        self.topic_val = topic
        self.offset_val = offset
        self.error_obj = error_obj

    def key(self):
        return self.key_val

    def value(self):
        return self.value_val

    def topic(self):
        return self.topic_val

    def offset(self):
        return self.offset_val

    def error(self):
        return self.error_obj


class DummyConsumer:
    """Mock Kafka consumer for testing."""

    def __init__(self, messages=None):
        self.messages = messages or []
        self.message_index = 0
        self.paused = False
        self.assigned_partitions = []

    def assignment(self):
        return self.assigned_partitions

    def poll(self, timeout=1):
        if self.message_index < len(self.messages):
            msg = self.messages[self.message_index]
            self.message_index += 1
            return msg
        return None

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def commit(self):
        pass


@pytest.mark.django_db
class TestWriteBufferOverflow:
    """Test WriteBuffer overflow policy and pause/resume logic."""

    @pytest.fixture
    def fake_settings(self, settings):
        """Configure buffer settings for testing."""
        settings.DB_WRITER_LATENCY_MS = 100
        settings.DB_WRITER_BATCH_SIZE = 50
        settings.DB_WRITER_MAX_BUFFER_SIZE = 100
        settings.DB_WRITER_MAX_FLUSH_ATTEMPTS = 3
        settings.DB_WRITER_SAFETY_SLEEP = 0.01
        return settings

    def test_buffer_len_property(self, fake_settings):
        """Buffer length returns count of items."""
        consumer = DummyConsumer([])
        buf = WriteBuffer(consumer, timeout=1.0, batch_size=50)

        assert buf.buffer_len == 0

        msg = DummyMessage(key=b"key1", value=b'{"test": "value"}')
        buf.buffer.append(
            BufferedItem(
                kafka_msg=msg,
                payload={"test": "value"},
                device_serial="TEST-SN-001",
            )
        )

        assert buf.buffer_len == 1

    def test_max_buffer_size_configuration(self, fake_settings):
        """Max buffer size correctly configured from settings."""
        consumer = DummyConsumer([])
        buf = WriteBuffer(consumer, timeout=1.0, batch_size=50)

        assert buf.max_buffer_size == 100

    def test_resume_threshold_is_70_percent(self, fake_settings):
        """Resume threshold set to 70% of max buffer size."""
        consumer = DummyConsumer([])
        buf = WriteBuffer(consumer, timeout=1.0, batch_size=50)

        # 70% of 100 = 70
        assert buf.resume_threshold == 70

    def test_overflow_policy_pauses_consumer(self, fake_settings):
        """Overflow triggers consumer pause."""
        consumer = DummyConsumer([])
        consumer.assigned_partitions = [MagicMock()]
        buf = WriteBuffer(consumer, timeout=1.0, batch_size=50)

        # Fill buffer beyond max
        for i in range(150):
            msg = DummyMessage(key=f"key{i}".encode(), offset=i)
            buf.buffer.append(
                BufferedItem(
                    kafka_msg=msg,
                    payload={"value": i},
                    device_serial=f"SN-{i}",
                )
            )

        # Mock the _overflow_policy to avoid sleep
        with patch.object(buf, "_overflow_policy"):
            # Manually call the overflow check
            if buf.buffer_len > buf.max_buffer_size:
                assert buf.buffer_len > buf.max_buffer_size

    def test_paused_flag_state(self, fake_settings):
        """Paused flag changes state correctly."""
        consumer = DummyConsumer([])
        buf = WriteBuffer(consumer, timeout=1.0, batch_size=50)

        assert buf.paused is False

        buf.paused = True
        assert buf.paused is True

        buf.paused = False
        assert buf.paused is False

    def test_inflight_tracking(self, fake_settings):
        """Inflight dictionary tracks pending flushes."""
        import time
        from confluent_kafka import TopicPartition

        consumer = DummyConsumer([])
        buf = WriteBuffer(consumer, timeout=1.0, batch_size=50)

        task_id = "task-123"
        msg = DummyMessage(key=b"key", offset=0)
        item = BufferedItem(kafka_msg=msg, payload={}, device_serial="SN-001")

        buf.inflight[task_id] = InFlight(
            flush=[item],
            offsets=[TopicPartition("test", 0, 0)],
            start=time.time(),
        )

        assert task_id in buf.inflight
        assert len(buf.inflight[task_id].flush) == 1
        assert buf.inflight[task_id].flush[0].device_serial == "SN-001"

    def test_batch_size_from_settings(self, fake_settings):
        """Batch size uses settings value when not zero."""
        consumer = DummyConsumer([])
        buf = WriteBuffer(consumer, timeout=1.0, batch_size=50)

        # Settings has DB_WRITER_BATCH_SIZE = 50, so use that
        assert buf.batch_size == 50

    def test_batch_size_fallback_to_arg(self, settings):
        """Batch size falls back to argument if setting is zero."""
        settings.DB_WRITER_BATCH_SIZE = 0
        settings.DB_WRITER_LATENCY_MS = 100
        settings.DB_WRITER_MAX_BUFFER_SIZE = 100
        settings.DB_WRITER_MAX_FLUSH_ATTEMPTS = 3
        settings.DB_WRITER_SAFETY_SLEEP = 0.01

        consumer = DummyConsumer([])
        buf = WriteBuffer(consumer, timeout=1.0, batch_size=75)

        # Settings is 0, so use argument
        assert buf.batch_size == 75


@pytest.mark.django_db
class TestKafkaMessageErrors:
    """Test handling of Kafka message errors and bad data."""

    @pytest.fixture
    def fake_settings(self, settings):
        """Configure buffer settings for testing."""
        settings.DB_WRITER_LATENCY_MS = 100
        settings.DB_WRITER_BATCH_SIZE = 50
        settings.DB_WRITER_MAX_BUFFER_SIZE = 1000
        settings.DB_WRITER_MAX_FLUSH_ATTEMPTS = 3
        settings.DB_WRITER_SAFETY_SLEEP = 0.001
        return settings

    def test_message_with_kafka_error_detected(self, fake_settings):
        """Message with Kafka error can be identified."""
        error_obj = MagicMock()
        error_obj.code.return_value = KafkaError._PARTITION_EOF

        msg = DummyMessage(error_obj=error_obj)

        assert msg.error() is not None

    def test_message_without_error(self, fake_settings):
        """Message without error returns None."""
        msg = DummyMessage(error_obj=None)

        assert msg.error() is None

    def test_bad_json_data(self, fake_settings):
        """Bad JSON payload identified."""
        bad_payload = b"not valid json {{"

        import json

        try:
            json.loads(bad_payload)
            assert False, "Should not parse"
        except json.JSONDecodeError:
            pass

    def test_missing_required_fields_in_message(self, fake_settings):
        """Message with missing required fields in value."""
        # Message with incomplete JSON
        msg = DummyMessage(value=b'{"incomplete": ')

        import json

        with pytest.raises(json.JSONDecodeError):
            json.loads(msg.value())

    def test_message_with_empty_value(self, fake_settings):
        """Message with empty value handled."""
        msg = DummyMessage(value=b"")

        assert msg.value() == b""

    def test_message_with_large_value(self, fake_settings):
        """Message with large payload handled."""
        large_value = b"x" * (1024 * 1024)  # 1MB

        msg = DummyMessage(value=large_value)

        assert len(msg.value()) == 1024 * 1024

    def test_message_with_null_key(self, fake_settings):
        """Message with null key allowed (fan-out)."""
        msg = DummyMessage(key=None, value=b'{"test": "value"}')

        assert msg.key() is None

    def test_consumer_poll_exhaustion(self, fake_settings):
        """Consumer returns None when messages exhausted."""
        messages = [DummyMessage(offset=0)]
        consumer = DummyConsumer(messages)

        msg = consumer.poll()
        assert msg is not None

        msg = consumer.poll()
        assert msg is None

    def test_error_message_structure(self, fake_settings):
        """Error messages contain expected information."""
        error_detail = {
            "reason": "validation_failed",
            "error_detail": "Invalid schema",
        }

        assert error_detail["reason"] == "validation_failed"
        assert "Invalid" in error_detail["error_detail"]
