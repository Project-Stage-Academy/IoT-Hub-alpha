"""
Simple tests for mock infrastructure in apps.telemetry.mocks.
Tests the mocking utilities used in integration testing.
"""

import pytest
from datetime import datetime
from apps.telemetry.mocks import (
    # Time mocks
    MockClock,
    TimeFreeze,
    # MQTT mocks
    MockMQTTClient,
    MockBroker,
    get_mqtt_client,
    reset_mock_broker,
    get_mock_broker_messages,
    # Helpers
    TelemetryBuilder,
    RuleBuilder,
    random_serial_number,
    random_device_id,
    random_telemetry_value,
)


class TestTelemetryBuilder:
    """Test TelemetryBuilder fluent API"""

    def test_builder_default_values(self):
        """Test builder creates valid telemetry with defaults"""
        telemetry = TelemetryBuilder().build()

        assert "serial_number" in telemetry
        assert "value" in telemetry
        assert "timestamp" in telemetry
        assert telemetry["schema_version"] == "1.0"

    def test_builder_with_serial(self):
        """Test setting device serial"""
        telemetry = TelemetryBuilder().with_serial("TEMP-SN-001").build()

        assert telemetry["serial_number"] == "TEMP-SN-001"

    def test_builder_with_value(self):
        """Test setting telemetry value"""
        telemetry = TelemetryBuilder().with_value(42.5).build()

        assert telemetry["value"] == 42.5

    def test_builder_with_timestamp(self):
        """Test setting custom timestamp"""
        timestamp = "2026-03-01T12:00:00"
        telemetry = TelemetryBuilder().with_timestamp(timestamp).build()

        assert telemetry["timestamp"] == timestamp

    def test_builder_with_schema_version(self):
        """Test setting schema version"""
        telemetry = TelemetryBuilder().with_schema_version("2.0").build()

        assert telemetry["schema_version"] == "2.0"

    def test_builder_with_custom_field(self):
        """Test adding custom fields"""
        telemetry = TelemetryBuilder().with_field("custom_key", "custom_value").build()

        assert telemetry["custom_key"] == "custom_value"

    def test_builder_with_multiple_fields(self):
        """Test adding multiple custom fields"""
        telemetry = (
            TelemetryBuilder()
            .with_fields({"location": "Lab A", "unit": "celsius"})
            .build()
        )

        assert telemetry["location"] == "Lab A"
        assert telemetry["unit"] == "celsius"

    def test_builder_build_json(self):
        """Test building JSON string"""
        json_str = TelemetryBuilder().build_json()

        assert isinstance(json_str, str)
        assert "serial_number" in json_str
        assert "value" in json_str

    def test_builder_build_bytes(self):
        """Test building bytes"""
        data_bytes = TelemetryBuilder().build_bytes()

        assert isinstance(data_bytes, bytes)
        # Should be valid JSON when decoded
        assert data_bytes.decode().startswith("{")


class TestRuleBuilder:
    """Test RuleBuilder fluent API"""

    def test_builder_default_values(self):
        """Test builder creates valid rule with defaults"""
        rule = RuleBuilder().build()

        assert "name" in rule
        assert "device_id" in rule
        assert "condition" in rule
        assert rule["is_active"] is True

    def test_builder_with_name(self):
        """Test setting rule name"""
        rule = RuleBuilder().with_name("Temperature Alert").build()

        assert rule["name"] == "Temperature Alert"

    def test_builder_with_threshold(self):
        """Test setting threshold value"""
        rule = RuleBuilder().with_threshold(30.0).build()

        assert rule["condition"]["threshold"] == 30.0

    def test_builder_with_operator(self):
        """Test setting comparison operator"""
        rule = RuleBuilder().with_operator("lt").build()

        assert rule["condition"]["operator"] == "lt"

    def test_builder_with_invalid_operator(self):
        """Test invalid operator raises ValueError"""
        with pytest.raises(ValueError):
            RuleBuilder().with_operator("invalid").build()

    def test_builder_with_window_seconds(self):
        """Test setting sliding window"""
        rule = RuleBuilder().with_window_seconds(600).build()

        assert rule["condition"]["window_seconds"] == 600

    def test_builder_with_occurrences(self):
        """Test setting occurrence count"""
        rule = RuleBuilder().with_occurrences(3).build()

        assert rule["condition"]["occurrences"] == 3

    def test_builder_with_inactive(self):
        """Test disabling rule"""
        rule = RuleBuilder().with_active(False).build()

        assert rule["is_active"] is False


class TestRandomHelpers:
    """Test randomization helpers"""

    def test_random_serial_number_default(self):
        """Test random serial number generation"""
        serial = random_serial_number()

        assert serial.startswith("SN-")
        assert len(serial) == 9  # "SN-" + 6 chars

    def test_random_serial_number_custom_prefix(self):
        """Test serial number with custom prefix"""
        serial = random_serial_number(prefix="TEMP")

        assert serial.startswith("TEMP-")

    def test_random_device_id(self):
        """Test random device UUID generation"""
        device_id = random_device_id()

        assert device_id is not None
        # Should be valid UUID
        assert len(str(device_id)) == 36

    def test_random_telemetry_value_default(self):
        """Test random telemetry value in default range"""
        value = random_telemetry_value()

        assert 0 <= value <= 100

    def test_random_telemetry_value_custom_range(self):
        """Test random telemetry value in custom range"""
        value = random_telemetry_value(min_val=20, max_val=30)

        assert 20 <= value <= 30


class TestMockClock:
    """Test MockClock time control"""

    def test_clock_initialization(self):
        """Test clock initializes with default time"""
        clock = MockClock()
        current = clock.current_time()

        assert current.year == 2026
        assert current.month == 3
        assert current.day == 1

    def test_clock_set_time_datetime(self):
        """Test setting clock to specific datetime"""
        clock = MockClock()
        new_time = datetime(2026, 3, 15, 14, 30, 0)

        clock.set_time(new_time)
        assert clock.current_time() == new_time

    def test_clock_set_time_string(self):
        """Test setting clock with ISO format string"""
        clock = MockClock()
        clock.set_time("2026-03-15T14:30:00")

        assert clock.current_time().day == 15
        assert clock.current_time().hour == 14

    def test_clock_advance_seconds(self):
        """Test advancing clock by seconds"""
        clock = MockClock()
        original = clock.current_time()

        clock.advance(3600)  # 1 hour
        advanced = clock.current_time()

        assert (advanced - original).total_seconds() == 3600

    def test_clock_advance_minutes(self):
        """Test advancing clock by minutes"""
        clock = MockClock()
        original = clock.current_time()

        clock.advance_minutes(30)
        advanced = clock.current_time()

        assert (advanced - original).total_seconds() == 1800

    def test_clock_advance_hours(self):
        """Test advancing clock by hours"""
        clock = MockClock()
        original = clock.current_time()

        clock.advance_hours(2)
        advanced = clock.current_time()

        assert (advanced - original).total_seconds() == 7200

    def test_clock_advance_days(self):
        """Test advancing clock by days"""
        clock = MockClock()
        original = clock.current_time()

        clock.advance_days(1)
        advanced = clock.current_time()

        assert (advanced - original).total_seconds() == 86400

    def test_clock_reset(self):
        """Test resetting clock to default"""
        clock = MockClock()
        clock.advance_hours(24)

        clock.reset()
        current = clock.current_time()

        assert current.month == 3
        assert current.day == 1

    def test_clock_is_past(self):
        """Test checking if time is past"""
        clock = MockClock()
        future_time = datetime(2026, 3, 2, 12, 0, 0)

        assert not clock.is_past(future_time)
        clock.advance_days(1)
        assert clock.is_past(future_time)

    def test_clock_is_future(self):
        """Test checking if time is in future"""
        clock = MockClock()
        future_time = datetime(2026, 3, 2, 12, 0, 0)

        assert clock.is_future(future_time)
        clock.advance_days(2)
        assert not clock.is_future(future_time)

    def test_clock_time_until(self):
        """Test calculating seconds until time"""
        clock = MockClock()
        target = datetime(2026, 3, 1, 13, 0, 0)

        seconds = clock.time_until(target)
        assert seconds == 3600  # 1 hour


class TestTimeFreeze:
    """Test TimeFreeze context manager"""

    def test_time_freeze_context(self):
        """Test TimeFreeze context manager"""
        with TimeFreeze("2026-03-01T12:00:00") as clock:
            assert clock.current_time().hour == 12
            clock.advance_hours(1)
            assert clock.current_time().hour == 13

    def test_time_freeze_resets_after(self):
        """Test TimeFreeze resets clock after context"""
        with TimeFreeze("2026-03-15T12:00:00") as clock:
            assert clock.current_time().day == 15

        # After context exits, clock should be reset to default
        clock_after = MockClock().current_time()
        assert clock_after.day == 1  # Default is March 1st


class TestMockMQTTClient:
    """Test MockMQTTClient MQTT mock"""

    def test_mqtt_client_creation(self):
        """Test creating MQTT client"""
        client = MockMQTTClient(client_id="test-001")

        assert client.client_id == "test-001"
        assert not client.is_connected()

    def test_mqtt_client_connect(self):
        """Test connecting MQTT client"""
        client = MockMQTTClient()

        client.connect("localhost", 1883)
        assert client.is_connected()

    def test_mqtt_client_disconnect(self):
        """Test disconnecting MQTT client"""
        client = MockMQTTClient()
        client.connect("localhost")

        client.disconnect()
        assert not client.is_connected()

    def test_mqtt_client_subscribe(self):
        """Test subscribing to topic"""
        client = MockMQTTClient()
        client.connect("localhost")

        mid, qos = client.subscribe("sensors/temp/data")
        assert mid == 0
        assert qos == [0]

    def test_mqtt_client_publish(self):
        """Test publishing message"""
        reset_mock_broker()
        client = MockMQTTClient(broker_id="test")
        client.connect("localhost")

        client.publish("sensors/temp", b'{"value": 25.5}')
        messages = client.get_published_messages("sensors/temp")

        assert len(messages) == 1
        assert messages[0]["payload"] == b'{"value": 25.5}'

    def test_mqtt_client_publish_dict(self):
        """Test publishing dict (auto-convert to JSON)"""
        reset_mock_broker("dict-test")
        client = MockMQTTClient(broker_id="dict-test")
        client.connect("localhost")

        client.publish("sensors/temp", {"value": 25.5})
        messages = client.get_published_messages("sensors/temp")

        assert len(messages) == 1
        assert b"25.5" in messages[0]["payload"]

    def test_mqtt_client_not_connected_raises(self):
        """Test publish raises when not connected"""
        client = MockMQTTClient()

        with pytest.raises(RuntimeError):
            client.publish("sensors/temp", b"test")

    def test_mqtt_client_callbacks(self):
        """Test MQTT client callbacks"""
        client = MockMQTTClient()

        connect_called = []

        def on_connect(c, u, f, r):
            connect_called.append(True)

        client.set_on_connect(on_connect)
        client.connect("localhost")

        assert len(connect_called) == 1


class TestMockBroker:
    """Test MockBroker message persistence"""

    def test_broker_publish_and_retrieve(self):
        """Test publishing and retrieving messages"""
        broker = MockBroker(broker_id="test")

        broker.publish("topic/1", b"message1")
        broker.publish("topic/1", b"message2")

        messages = broker.get_messages("topic/1")
        assert len(messages) == 2

    def test_broker_clear(self):
        """Test clearing broker messages"""
        broker = MockBroker(broker_id="test")
        broker.publish("topic/1", b"message")

        broker.clear()
        messages = broker.get_messages("topic/1")

        assert len(messages) == 0

    def test_broker_multiple_topics(self):
        """Test broker with multiple topics"""
        broker = MockBroker(broker_id="test")

        broker.publish("sensors/temp", b"temp")
        broker.publish("sensors/humidity", b"humidity")

        temp_msgs = broker.get_messages("sensors/temp")
        humidity_msgs = broker.get_messages("sensors/humidity")

        assert len(temp_msgs) == 1
        assert len(humidity_msgs) == 1


class TestGetMQTTClient:
    """Test get_mqtt_client factory function"""

    def test_get_mqtt_client_returns_mock(self):
        """Test get_mqtt_client returns MockMQTTClient"""
        client = get_mqtt_client(client_id="factory-test")

        # Should be MockMQTTClient since paho-mqtt might not be available
        assert hasattr(client, "connect")
        assert hasattr(client, "publish")
        assert hasattr(client, "subscribe")


class TestMockBrokerGlobal:
    """Test global mock broker functions"""

    def test_reset_mock_broker(self):
        """Test resetting mock broker"""
        client = MockMQTTClient(broker_id="reset-test")
        client.connect("localhost")
        client.publish("test/topic", b"message")

        reset_mock_broker("reset-test")
        messages = get_mock_broker_messages(broker_id="reset-test", topic="test/topic")

        assert len(messages) == 0

    def test_get_mock_broker_messages(self):
        """Test retrieving all broker messages"""
        reset_mock_broker("msg-test")
        client = MockMQTTClient(broker_id="msg-test")
        client.connect("localhost")

        client.publish("topic1", b"msg1")
        client.publish("topic2", b"msg2")

        all_messages = get_mock_broker_messages(broker_id="msg-test")

        assert "topic1" in all_messages
        assert "topic2" in all_messages

    def test_get_mock_broker_messages_single_topic(self):
        """Test retrieving messages from specific topic"""
        reset_mock_broker("single-test")
        client = MockMQTTClient(broker_id="single-test")
        client.connect("localhost")

        client.publish("specific/topic", b"message")
        messages = get_mock_broker_messages(
            broker_id="single-test", topic="specific/topic"
        )

        assert len(messages) == 1
