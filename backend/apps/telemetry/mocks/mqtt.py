"""
Mock MQTT Client for testing MQTT adapter without real broker.
Follows pattern from mock_kafka.py - thread-safe in-memory message store.
"""

import json
import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("telemetry.mock_mqtt")

# Global in-memory message store per broker
# Structure: {broker_id: {topic: [{"payload": bytes, "qos": int,
# "timestamp": float}, ...]}}
_brokers: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(
    lambda: defaultdict(list)
)
_brokers_lock = Lock()


class MockMQTTMessage:
    """
    Mock MQTT message mimicking paho-mqtt.client.MQTTMessage interface.

    Attributes:
        topic: Topic name message was published to
        payload: Message bytes (usually UTF-8 encoded string)
        qos: Quality of Service level (0, 1, or 2)
        retain: Whether message is retained
        mid: Message ID (for matching publish/publish_complete)
        userdata: Custom user data attached to client
    """

    def __init__(
        self,
        topic: str,
        payload: bytes,
        qos: int = 0,
        retain: bool = False,
        mid: int = 0,
        userdata: Any = None,
    ):
        self.topic = topic
        self.payload = payload
        self.qos = qos
        self.retain = retain
        self.mid = mid
        self.userdata = userdata
        self.timestamp = time.time()


class MockBroker:
    """
    Global MQTT broker simulating message persistence.

    Stores published messages by broker_id (for multi-broker testing).
    Coordinates message delivery between multiple mock clients.
    Thread-safe via _brokers_lock.
    """

    def __init__(self, broker_id: str = "default"):
        self.broker_id = broker_id

    def publish(self, topic: str, payload: bytes, qos: int = 0) -> None:
        """Store published message."""
        with _brokers_lock:
            _brokers[self.broker_id][topic].append(
                {
                    "payload": payload,
                    "qos": qos,
                    "timestamp": time.time(),
                }
            )
            payload_size = len(payload)
            logger.debug(f"[{self.broker_id}] Published: {payload_size} bytes")

    def get_messages(self, topic: str) -> List[Dict[str, Any]]:
        """Retrieve all messages published to topic."""
        with _brokers_lock:
            return _brokers[self.broker_id].get(topic, [])

    def clear(self) -> None:
        """Clear all messages from broker."""
        with _brokers_lock:
            _brokers[self.broker_id].clear()
            logger.info(f"[{self.broker_id}] Broker cleared")


class MockMQTTClient:
    """
    Mock MQTT Client mimicking paho-mqtt.client.Client interface.

    Replaces paho-mqtt when not available. Stores published messages
    in thread-safe global broker. Supports callbacks for testing
    async behavior.

    Thread Safety:
    - All broker access protected by _brokers_lock
    - Callback storage is per-client (no lock needed)

    Supported Methods:
    - connect(host, port, keepalive): No-op, always succeeds
    - disconnect(): No-op, always succeeds
    - subscribe(topic, qos): Records subscription
    - unsubscribe(topic): Records unsubscription
    - publish(topic, payload, qos, retain): Publishes to broker
    - loop_start() / loop_stop(): Manages callback thread
    - set_on_connect / set_on_message / set_on_disconnect: Register callbacks
    - is_connected(): Returns connection state

    Callbacks:
    - on_connect(client, userdata, flags, rc): Called on successful connect
    - on_message(client, userdata, msg): Called when message arrives
    - on_disconnect(client, userdata, rc): Called on disconnect

    Usage:
        client = MockMQTTClient("test-device")
        client.set_on_message(my_callback)
        client.connect("localhost", 1883)
        client.subscribe("sensors/+/data")
        client.publish("sensors/temp/data", b'{"value": 25.5}')
        client.disconnect()
    """

    def __init__(
        self,
        client_id: str = "",
        userdata: Any = None,
        broker_id: str = "default",
    ):
        self.client_id = client_id
        self.userdata = userdata
        self.broker_id = broker_id
        self.broker = MockBroker(broker_id)
        self._connected = False
        self._subscribed_topics: Dict[str, int] = {}  # topic -> qos
        self._on_connect: Optional[Callable] = None
        self._on_message: Optional[Callable] = None
        self._on_disconnect: Optional[Callable] = None
        self._message_id = 0
        log_msg = f"MockMQTTClient init (id: {client_id}, broker: {broker_id})"
        logger.info(log_msg)

    def connect(self, host: str, port: int = 1883, keepalive: int = 60) -> None:
        """Connect to broker (no-op, always succeeds)."""
        self._connected = True
        logger.info(f"[{self.client_id}] Connected to {host}:{port}")

        # Simulate on_connect callback
        if self._on_connect:
            self._on_connect(self, self.userdata, {}, 0)

    def disconnect(self) -> None:
        """Disconnect from broker (no-op)."""
        self._connected = False
        logger.info(f"[{self.client_id}] Disconnected")

        # Simulate on_disconnect callback
        if self._on_disconnect:
            self._on_disconnect(self, self.userdata, 0)

    def subscribe(self, topic: str, qos: int = 0) -> tuple:
        """Subscribe to topic."""
        if not self._connected:
            raise RuntimeError(f"[{self.client_id}] Not connected")

        self._subscribed_topics[topic] = qos
        logger.info(f"[{self.client_id}] Subscribed to {topic} (QoS: {qos})")
        return (0, [qos])  # (mid, granted_qos)

    def unsubscribe(self, topic: str) -> tuple:
        """Unsubscribe from topic."""
        if topic in self._subscribed_topics:
            del self._subscribed_topics[topic]
            logger.info(f"[{self.client_id}] Unsubscribed from {topic}")
        return (0,)  # (mid,)

    def publish(
        self,
        topic: str,
        payload: Any = None,
        qos: int = 0,
        retain: bool = False,
    ) -> "MQTTMessageInfo":
        """Publish message to topic."""
        if not self._connected:
            raise RuntimeError(f"[{self.client_id}] Not connected")

        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        elif isinstance(payload, dict):
            payload = json.dumps(payload).encode("utf-8")
        elif payload is None:
            payload = b""

        self._message_id += 1
        self.broker.publish(topic, payload, qos)
        msg = f"[{self.client_id}] Published to {topic}: {len(payload)} bytes"
        logger.debug(msg)

        # Return MQTTMessageInfo-like object
        return MQTTMessageInfo(self._message_id)

    def set_on_connect(self, func: Callable) -> None:
        """Register on_connect callback."""
        self._on_connect = func
        logger.debug(f"[{self.client_id}] Registered on_connect callback")

    def set_on_message(self, func: Callable) -> None:
        """Register on_message callback."""
        self._on_message = func
        logger.debug(f"[{self.client_id}] Registered on_message callback")

    def set_on_disconnect(self, func: Callable) -> None:
        """Register on_disconnect callback."""
        self._on_disconnect = func
        logger.debug(f"[{self.client_id}] Registered on_disconnect callback")

    def loop_start(self) -> None:
        """Start network loop (no-op for mock)."""
        logger.debug(f"[{self.client_id}] Loop started")

    def loop_stop(self) -> None:
        """Stop network loop (no-op for mock)."""
        logger.debug(f"[{self.client_id}] Loop stopped")

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    def get_published_messages(self, topic: str) -> List[Dict[str, Any]]:
        """Retrieve all messages published to topic (test utility)."""
        return self.broker.get_messages(topic)


class MQTTMessageInfo:
    """Mock MQTTMessageInfo returned by client.publish()."""

    def __init__(self, mid: int):
        self.mid = mid
        self.is_queued = lambda: False
        self.wait_for_publish = lambda: None


def get_mqtt_client(
    client_id: str = "", userdata: Any = None, broker_id: str = "default", **kwargs
):
    """
    Factory function returning real or mock MQTT client.

    Strategy:
    1. Try importing paho.mqtt.client (real paho-mqtt)
    2. If ImportError: Fall back to MockMQTTClient
    3. Logs which implementation is being used

    Args:
        client_id: Client identifier
        userdata: User data passed to callbacks
        broker_id: Broker ID for multi-broker testing
        **kwargs: Additional arguments passed to client

    Returns:
        paho.mqtt.client.Client if available, MockMQTTClient otherwise

    Usage:
        client = get_mqtt_client(client_id="sensor-001")
        client.connect("localhost", 1883)
        client.publish("sensors/temp", b'{"value": 25.5}')
    """
    try:
        import paho.mqtt.client as mqtt

        logger.info("Using real paho-mqtt Client")
        return mqtt.Client(client_id=client_id, userdata=userdata, **kwargs)
    except ImportError:
        logger.info("paho-mqtt not available, using MockMQTTClient")
        return MockMQTTClient(
            client_id=client_id, userdata=userdata, broker_id=broker_id
        )


def reset_mock_broker(broker_id: str = "default") -> None:
    """
    Clear all messages from broker (test utility).

    Thread-safe reset of broker messages. Call between tests to ensure
    clean state.

    Args:
        broker_id: Broker ID to reset

    Usage:
        # In pytest fixture
        def setup():
            reset_mock_broker()
            # ... run test ...
    """
    with _brokers_lock:
        _brokers[broker_id].clear()
    logger.info(f"Mock broker '{broker_id}' reset")


def get_mock_broker_messages(
    broker_id: str = "default", topic: Optional[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retrieve all messages from broker (test assertion helper).

    Thread-safe read of broker messages. Returns dict of {topic: messages}.

    Args:
        broker_id: Broker ID to retrieve from
        topic: Optional specific topic (returns only that topic's messages)

    Returns:
        Dict[topic -> List[message dicts]] or List[messages] if topic specified

    Usage:
        client.publish("sensors/temp", b'{"value": 25.5}')
        messages = get_mock_broker_messages(topic="sensors/temp")
        assert len(messages) == 1
        payload = json.loads(messages[0]["payload"])
        assert payload["value"] == 25.5
    """
    with _brokers_lock:
        if topic:
            return _brokers[broker_id].get(topic, [])
        return dict(_brokers[broker_id])
