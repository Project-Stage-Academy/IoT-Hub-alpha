"""
Mocking infrastructure for IoT Hub testing.

Provides mock implementations for external dependencies:
- MQTT clients (paho-mqtt)
- Virtual MQTT devices
- Kafka producer/consumer
- Time control for testing time-dependent behaviors
- Test data builders and assertion helpers
"""

from .mqtt import (
    MockMQTTMessage,
    MockMQTTClient,
    MockBroker,
    get_mqtt_client,
    reset_mock_broker,
    get_mock_broker_messages,
)
from .devices import (
    VirtualDevice,
    VirtualDeviceFactory,
    VirtualDeviceStatus,
)
from .time import (
    MockClock,
    TimeFreeze,
)
from .kafka import (
    MockMessage as MockKafkaMessage,
    MockProducer,
    MockConsumer,
    reset_mock_topics,
    get_mock_topic_messages,
    get_kafka_producer,
    get_kafka_consumer,
)
from .helpers import (
    TelemetryBuilder,
    RuleBuilder,
    assert_telemetry_published,
    assert_rule_triggered,
    random_serial_number,
    random_device_id,
    random_telemetry_value,
)

__all__ = [
    # MQTT mocks
    "MockMQTTMessage",
    "MockMQTTClient",
    "MockBroker",
    "get_mqtt_client",
    "reset_mock_broker",
    "get_mock_broker_messages",
    # Device mocks
    "VirtualDevice",
    "VirtualDeviceFactory",
    "VirtualDeviceStatus",
    # Time mocks
    "MockClock",
    "TimeFreeze",
    # Kafka mocks
    "MockKafkaMessage",
    "MockProducer",
    "MockConsumer",
    "reset_mock_topics",
    "get_mock_topic_messages",
    "get_kafka_producer",
    "get_kafka_consumer",
    # Helpers
    "TelemetryBuilder",
    "RuleBuilder",
    "assert_telemetry_published",
    "assert_rule_triggered",
    "random_serial_number",
    "random_device_id",
    "random_telemetry_value",
]
