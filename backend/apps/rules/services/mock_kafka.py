"""
Mock Kafka Producer/Consumer for local development.
Replaces confluent-kafka when not available.
"""

import json
import logging
import time
from collections import defaultdict
from threading import Lock
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("rules.mock_kafka")


# Global in-memory message store
_topics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
_topics_lock = Lock()


class MockMessage:
    """
    Mock Kafka message for testing without real Kafka broker.

    Mimics confluent_kafka.Message interface by providing value(),
    error(), and topic() methods. Used by MockProducer/MockConsumer
    to simulate message passing during unit tests.

    Attributes:
        topic_name: Kafka topic this message was produced to
        _value: Raw message bytes (JSON payload)
        offset: Partition offset (message sequence number)
        error_val: Error code if message is error indicator (None = success)
    """

    def __init__(self, topic: str, value: bytes, offset: int = 0):
        self.topic_name = topic
        self._value = value
        self.offset = offset
        self.error_val = None

    def value(self) -> bytes:
        return self._value

    def error(self) -> Optional[str]:
        return self.error_val

    def topic(self) -> str:
        return self.topic_name


class MockProducer:
    """
    Mock Kafka Producer for local development and testing.

    Replaces confluent_kafka.Producer when confluent-kafka is not installed.
    Stores produced messages in thread-safe global dict (_topics) for consumption
    by MockConsumer. Allows testing full Kafka pipeline without real broker.

    Thread Safety:
    - All operations protected by _topics_lock
    - Safe for concurrent producer/consumer threads

    Message Storage:
    - Messages stored in format: {"value": bytes, "offset": int,
      "timestamp": datetime, "key": str}
    - Each topic gets its own list in _topics defaultdict
    - Offset auto-incremented per message per topic

    Usage:
        producer = MockProducer()
        producer.send("my_topic", {"key": "value"})
        producer.flush()
    """

    def __init__(self, *args, **kwargs):
        # Handle both positional and keyword arguments
        if args and isinstance(args[0], dict):
            kwargs = args[0]
        self.topic_name = kwargs.get("default_topic")
        logger.info(f"MockProducer initialized (topic: {self.topic_name})")

    def send(
        self, topic: str, value: Dict[str, Any], key: Optional[str] = None
    ) -> None:
        """
        Produce message to topic (store in memory).

        Serializes dict to JSON bytes, wraps with metadata, and appends to topic list.
        Thread-safe via _topics_lock. Non-blocking - returns immediately after storing.

        Args:
            topic: Topic name to produce to
            value: Dict to serialize as JSON (usually event/telemetry data)
            key: Optional routing key (ignored in this mock, but accepted
                 for API compatibility)

        Side Effects:
        - Adds message to _topics[topic] list
        - Increments offset for topic
        - Records message timestamp
        """
        with _topics_lock:
            json_bytes = json.dumps(value).encode("utf-8")
            _topics[topic].append(
                {
                    "value": json_bytes,
                    "offset": len(_topics[topic]),
                    "timestamp": datetime.now(),
                    "key": key,
                }
            )
            logger.debug(f"Message produced to {topic}: {value}")

    def flush(self) -> None:
        """
        Flush pending messages (no-op for mock implementation).

        In real confluent_kafka, ensures all queued messages are sent before returning.
        In MockProducer, messages are stored immediately so flush is a no-op.
        Kept for API compatibility with confluent_kafka.Producer.
        """
        pass

    def close(self) -> None:
        """
        Close producer and release resources (no-op for mock implementation).

        In real confluent_kafka, flushes pending messages and closes connections.
        In MockProducer, no resources to release.
        Kept for API compatibility with confluent_kafka.Producer.
        """
        pass


class MockConsumer:
    """
    Mock Kafka Consumer for local development and testing.

    Replaces confluent_kafka.Consumer when confluent-kafka is not installed.
    Reads messages from thread-safe global _topics dict produced by MockProducer.
    Tracks per-topic offsets to simulate consumer group behavior.

    Consumer Behavior:
    - Maintains per-topic offset to track position
    - Each poll() advances offset if message available
    - Multiple consumers use same shared _topics (simulates single broker)
    - auto.offset.reset handling: supports "earliest" (default)

    Thread Safety:
    - All topic access protected by _topics_lock
    - Safe for concurrent producer/consumer threads
    - Each consumer instance has independent offset state

    Usage:
        consumer = MockConsumer({"group.id": "my-group"})
        consumer.subscribe(["my_topic"])
        while True:
            msg = consumer.poll(timeout_ms=1000)
            if msg: process(msg)
    """

    def __init__(self, *args, **kwargs):
        # Handle both positional and keyword arguments
        if args and isinstance(args[0], dict):
            kwargs = args[0]
        self.group_id = kwargs.get("group.id", "default-group")
        self.auto_offset_reset = kwargs.get("auto.offset.reset", "earliest")
        self.enable_auto_commit = kwargs.get("enable.auto.commit", True)
        self.subscribed_topics: List[str] = []
        self.offsets: Dict[str, int] = defaultdict(int)  # topic -> offset
        self.poll_timeout = 1.0
        logger.info(f"MockConsumer initialized (group: {self.group_id})")

    def subscribe(self, topics: List[str]) -> None:
        """
        Subscribe to list of topics for consumption.

        Sets subscribed_topics. Subsequent poll() calls will consume from these
        topics in order. Resets offsets to 0 for each topic unless existing
        offset already tracked (for re-subscription scenarios).

        Args:
            topics: List of topic names to consume from
                    (e.g., ["telemetry.clean", "events"])
        """
        self.subscribed_topics = topics
        logger.info(f"Subscribed to topics: {topics}")

    def poll(self, timeout_ms: float = 1000) -> Optional[MockMessage]:
        """
        Poll for next message from subscribed topics with timeout support.

        Iterates through subscribed_topics in order, checks if message is available
        at current offset. Returns first available message and advances offset.
        If no messages available in any topic, waits up to timeout_ms before
        returning None. Implements realistic timeout behavior for testing.

        Args:
            timeout_ms: Poll timeout in milliseconds. Will wait up to this long
                       for a message to appear in any subscribed topic.

        Returns:
            MockMessage if available, None if timeout elapsed with no messages.
            Message comes from first subscribed topic with available data at
            current offset.

        Side Effects:
        - Advances offset for topic if message returned
        - Does not advance offset if None returned (can retry same offset)
        - Blocks for up to timeout_ms if no messages available

        Example:
            consumer.subscribe(["my_topic"])
            msg = consumer.poll(1000)  # Wait up to 1 second
            if msg:
                data = json.loads(msg.value().decode("utf-8"))
                process(data)
        """
        timeout_s = timeout_ms / 1000.0
        start_time = time.time()
        poll_interval = 0.01  # 10ms between checks for realistic behavior

        # Poll with timeout - check periodically until timeout elapsed
        while time.time() - start_time < timeout_s:
            for topic in self.subscribed_topics:
                with _topics_lock:
                    messages = _topics.get(topic, [])
                    offset = self.offsets[topic]

                    if offset < len(messages):
                        msg_data = messages[offset]
                        self.offsets[topic] += 1
                        logger.debug(
                            f"Polled message from {topic} offset {offset}"
                        )
                        return MockMessage(
                            topic=topic,
                            value=msg_data["value"],
                            offset=offset,
                        )

            # No message found, sleep briefly before next check
            time.sleep(poll_interval)

        # Timeout elapsed with no messages available
        elapsed = time.time() - start_time
        logger.debug(
            f"Poll timeout after {elapsed:.2f}s (requested: {timeout_s}s)"
        )
        return None

    def close(self) -> None:
        """
        Close consumer and release resources (no-op for mock implementation).

        In real confluent_kafka, leaves consumer group and closes connections.
        In MockConsumer, no resources to release.
        Kept for API compatibility with confluent_kafka.Consumer.
        """
        logger.info(f"MockConsumer closed (group: {self.group_id})")


def reset_mock_topics() -> None:
    """
    Clear all messages from all topics (test utility function).

    Thread-safe reset of global _topics dict. Used between tests to ensure
    clean state. Must be called before each test to avoid message leakage
    from previous tests.

    Usage:
        # In test setUp or fixture
        reset_mock_topics()
        # ... run test ...
    """
    global _topics
    with _topics_lock:
        _topics.clear()
    logger.info("Mock topics reset")


def get_mock_topic_messages(topic: str) -> List[Dict[str, Any]]:
    """
    Retrieve all messages from topic for test assertions.

    Thread-safe read of _topics[topic]. Returns list of message dicts with structure:
    {"value": bytes, "offset": int, "timestamp": datetime, "key": str}

    Usage:
        producer.send("my_topic", {"status": "ok"})
        messages = get_mock_topic_messages("my_topic")
        assert len(messages) == 1
        data = json.loads(messages[0]["value"].decode("utf-8"))
        assert data["status"] == "ok"

    Args:
        topic: Topic name to retrieve messages from

    Returns:
        List of message dicts (empty list if topic has no messages)
    """
    with _topics_lock:
        return _topics.get(topic, [])


def get_kafka_producer(**kwargs):
    """
    Factory function that returns real or mock Kafka producer.

    Strategy:
    1. Try importing confluent_kafka.Producer (real Kafka)
    2. If ImportError (confluent-kafka not installed): fall back to MockProducer
    3. Logs which implementation is being used for debugging

    Returns:
        confluent_kafka.Producer if confluent-kafka installed,
        MockProducer otherwise

    Usage:
        producer = get_kafka_producer(
            bootstrap_servers="kafka:9092",
            default_topic="my_topic"
        )
        producer.send("my_topic", {"data": "value"})
    """
    try:
        from confluent_kafka import Producer

        logger.info("Using real Kafka Producer")
        return Producer(**kwargs)
    except ImportError:
        logger.info("confluent_kafka not available, using MockProducer")
        return MockProducer(**kwargs)


def get_kafka_consumer(**kwargs):
    """
    Factory function that returns real or mock Kafka consumer.

    Strategy:
    1. Try importing confluent_kafka.Consumer (real Kafka)
    2. If ImportError (confluent-kafka not installed): fall back to MockConsumer
    3. Logs which implementation is being used for debugging

    Returns:
        confluent_kafka.Consumer if confluent-kafka installed,
        MockConsumer otherwise

    Usage:
        consumer = get_kafka_consumer(
            bootstrap_servers="kafka:9092",
            group_id="my-group",
            auto_offset_reset="earliest"
        )
        consumer.subscribe(["my_topic"])
        while True:
            msg = consumer.poll(1000)
            if msg: process(msg)
    """
    try:
        from confluent_kafka import Consumer

        logger.info("Using real Kafka Consumer")
        return Consumer(**kwargs)
    except ImportError:
        logger.info("confluent_kafka not available, using MockConsumer")
        return MockConsumer(**kwargs)
