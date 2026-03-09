"""
Basic integration tests for ingestion pipeline.

Simplified integration tests focusing on core scenarios
without strict timing assumptions.
"""

import json
import time
import pytest

from telemetry.mocks import (
    MockMQTTClient,
    VirtualDeviceFactory,
    TelemetryBuilder,
    RuleBuilder,
    get_mock_broker_messages,
    random_serial_number,
)


@pytest.fixture
def mqtt_broker():
    """Provide isolated MQTT broker."""
    return f"test-{random_serial_number()}"


@pytest.fixture
def mqtt_setup(mqtt_broker):
    """Setup MQTT infrastructure."""
    client = MockMQTTClient(client_id="test", broker_id=mqtt_broker)
    client.connect("localhost", 1883)
    factory = VirtualDeviceFactory(client)

    def get_messages(topic=None):
        return get_mock_broker_messages(mqtt_broker, topic)

    yield {
        "client": client,
        "factory": factory,
        "get_messages": get_messages,
    }

    client.disconnect()


# ============================================================================
# Basic Integration Tests
# ============================================================================


class TestBasicMQTTPublishing:
    """Test basic MQTT publishing."""

    def test_single_device_publishes(self, mqtt_setup):
        """Single device successfully publishes."""
        device = mqtt_setup["factory"].create_temperature_sensor("TEMP-001")
        device.start()
        time.sleep(0.2)
        device.stop()

        topic = f"sensors/{device.serial_number}/data"
        messages = mqtt_setup["get_messages"](topic)

        assert len(messages) > 0
        assert device.message_count > 0

    def test_multiple_devices_publish(self, mqtt_setup):
        """Multiple devices publish independently."""
        devices = mqtt_setup["factory"].create_device_group(
            count=3, device_type="temperature_sensor", serial_prefix="TEMP"
        )

        for device in devices:
            device.start()

        time.sleep(0.2)

        for device in devices:
            device.stop()

        # Verify all published
        for device in devices:
            topic = f"sensors/{device.serial_number}/data"
            messages = mqtt_setup["get_messages"](topic)
            assert len(messages) > 0

    def test_telemetry_message_structure(self, mqtt_setup):
        """Telemetry messages have correct structure."""
        device = mqtt_setup["factory"].create_temperature_sensor("TEMP-001")
        device.start()
        time.sleep(0.1)
        device.stop()

        topic = f"sensors/{device.serial_number}/data"
        messages = mqtt_setup["get_messages"](topic)

        for msg in messages:
            payload = json.loads(msg["payload"])
            assert "serial_number" in payload
            assert "value" in payload
            assert "timestamp" in payload
            assert "device_type" in payload


class TestDataBuilders:
    """Test data builders."""

    def test_telemetry_builder(self):
        """TelemetryBuilder works correctly."""
        telemetry = TelemetryBuilder().with_serial("TEST-001").with_value(25.5).build()

        assert telemetry["serial_number"] == "TEST-001"
        assert telemetry["value"] == 25.5

    def test_rule_builder(self):
        """RuleBuilder works correctly."""
        rule = (
            RuleBuilder()
            .with_name("Test Rule")
            .with_threshold(30.0)
            .with_operator("gt")
            .build()
        )

        assert rule["name"] == "Test Rule"
        assert rule["condition"]["threshold"] == 30.0
        assert rule["condition"]["operator"] == "gt"

    def test_telemetry_json_serialization(self):
        """TelemetryBuilder serializes to JSON."""
        builder = TelemetryBuilder().with_serial("TEST-001").with_value(25.5)
        telemetry = builder.build_json()

        parsed = json.loads(telemetry)
        assert parsed["serial_number"] == "TEST-001"
        assert parsed["value"] == 25.5


class TestMQTTClient:
    """Test mock MQTT client."""

    def test_client_publish_retrieve(self, mqtt_setup):
        """Publish and retrieve messages."""
        client = mqtt_setup["client"]
        client.publish("test/topic", {"key": "value"})

        messages = mqtt_setup["get_messages"]("test/topic")
        assert len(messages) == 1

        payload = json.loads(messages[0]["payload"])
        assert payload["key"] == "value"

    def test_multiple_publishes(self, mqtt_setup):
        """Multiple publishes accumulate."""
        client = mqtt_setup["client"]

        for i in range(5):
            client.publish("test/topic", f"message-{i}".encode())

        messages = mqtt_setup["get_messages"]("test/topic")
        assert len(messages) == 5

    def test_different_topics_isolated(self, mqtt_setup):
        """Different topics are isolated."""
        client = mqtt_setup["client"]

        client.publish("topic1", b"data1")
        client.publish("topic2", b"data2")

        msg1 = mqtt_setup["get_messages"]("topic1")
        msg2 = mqtt_setup["get_messages"]("topic2")

        assert len(msg1) == 1
        assert len(msg2) == 1
        assert msg1[0]["payload"] == b"data1"
        assert msg2[0]["payload"] == b"data2"


class TestDeviceSimulator:
    """Test virtual device simulator."""

    def test_device_creation(self, mqtt_setup):
        """Create device successfully."""
        device = mqtt_setup["factory"].create_temperature_sensor("TEMP-001")
        assert device.serial_number == "TEMP-001"
        assert device.device_type == "temperature_sensor"

    def test_device_factory_types(self, mqtt_setup):
        """Factory creates different sensor types."""
        factory = mqtt_setup["factory"]

        temp = factory.create_temperature_sensor("T-001")
        vib = factory.create_vibration_sensor("V-001")
        cur = factory.create_current_sensor("C-001")

        assert temp.device_type == "temperature_sensor"
        assert vib.device_type == "vibration_sensor"
        assert cur.device_type == "current_sensor"

    def test_device_group_creation(self, mqtt_setup):
        """Create group of devices."""
        devices = mqtt_setup["factory"].create_device_group(
            count=3, device_type="temperature_sensor"
        )

        assert len(devices) == 3
        assert all(d.device_type == "temperature_sensor" for d in devices)


class TestEndToEndBasic:
    """Basic end-to-end scenarios."""

    def test_device_to_mqtt(self, mqtt_setup):
        """Device publishes to MQTT successfully."""
        device = mqtt_setup["factory"].create_temperature_sensor("TEMP-001")

        # Device publishes
        device.start()
        time.sleep(0.15)
        device.stop()

        # Verify on MQTT
        topic = f"sensors/{device.serial_number}/data"
        messages = mqtt_setup["get_messages"](topic)

        assert len(messages) > 0
        assert device.message_count == len(messages)

        # Verify message content
        for msg in messages:
            payload = json.loads(msg["payload"])
            assert payload["serial_number"] == "TEMP-001"
            assert isinstance(payload["value"], (int, float))

    def test_multiple_device_publishing(self, mqtt_setup):
        """Multiple devices publish simultaneously."""
        # Create 3 different sensor types
        temp = mqtt_setup["factory"].create_temperature_sensor("T-001")
        vib = mqtt_setup["factory"].create_vibration_sensor("V-001")
        cur = mqtt_setup["factory"].create_current_sensor("C-001")

        # All start publishing
        for device in [temp, vib, cur]:
            device.start()

        time.sleep(0.2)

        # All stop
        for device in [temp, vib, cur]:
            device.stop()

        # Verify all published
        for device in [temp, vib, cur]:
            topic = f"sensors/{device.serial_number}/data"
            messages = mqtt_setup["get_messages"](topic)
            assert len(messages) > 0
            assert device.message_count == len(messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
