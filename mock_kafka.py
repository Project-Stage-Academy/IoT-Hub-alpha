"""
Mock Kafka Producer/Consumer for local development.
Replaces confluent-kafka when not available.
"""

import json
import logging
from collections import defaultdict
from threading import Lock
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger("rules.mock_kafka")


# Global in-memory message store
_topics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
_topics_lock = Lock()


class MockMessage:
    """Mock Kafka message"""

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
    """Mock Kafka Producer - stores messages in memory"""

    def __init__(self, *args, **kwargs):
        # Handle both positional and keyword arguments
        if args and isinstance(args[0], dict):
            kwargs = args[0]
        self.topic_name = kwargs.get("default_topic")
        logger.info(f"MockProducer initialized (topic: {self.topic_name})")

    def send(
        self, topic: str, value: Dict[str, Any], key: Optional[str] = None
    ) -> None:
        """Send message to topic"""
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
        """Flush (no-op for mock)"""
        pass

    def close(self) -> None:
        """Close (no-op for mock)"""
        pass


class MockConsumer:
    """Mock Kafka Consumer - reads from in-memory topics"""

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
        """Subscribe to topics"""
        self.subscribed_topics = topics
        logger.info(f"Subscribed to topics: {topics}")

    def poll(self, timeout_ms: float = 1000) -> Optional[MockMessage]:
        """
        Poll for next message.
        Returns message if available, None otherwise.
        """
        timeout_s = timeout_ms / 1000.0

        for topic in self.subscribed_topics:
            with _topics_lock:
                messages = _topics.get(topic, [])
                offset = self.offsets[topic]

                if offset < len(messages):
                    msg_data = messages[offset]
                    self.offsets[topic] += 1
                    logger.debug(f"Polled message from {topic} offset {offset}")
                    return MockMessage(
                        topic=topic,
                        value=msg_data["value"],
                        offset=offset,
                    )

        # No message available
        logger.debug(f"No messages available (timeout: {timeout_s}s)")
        return None

    def close(self) -> None:
        """Close consumer"""
        logger.info(f"MockConsumer closed (group: {self.group_id})")


def reset_mock_topics() -> None:
    """Reset all mock topics (for testing)"""
    global _topics
    with _topics_lock:
        _topics.clear()
    logger.info("Mock topics reset")


def get_mock_topic_messages(topic: str) -> List[Dict[str, Any]]:
    """Get all messages from a topic (for testing)"""
    with _topics_lock:
        return _topics.get(topic, [])


def get_kafka_producer(**kwargs):
    """Factory function - returns MockProducer by default"""
    try:
        from confluent_kafka import Producer

        logger.info("Using real Kafka Producer")
        return Producer(**kwargs)
    except ImportError:
        logger.info("confluent_kafka not available, using MockProducer")
        return MockProducer(**kwargs)


def get_kafka_consumer(**kwargs):
    """Factory function - returns MockConsumer by default"""
    try:
        from confluent_kafka import Consumer

        logger.info("Using real Kafka Consumer")
        return Consumer(**kwargs)
    except ImportError:
        logger.info("confluent_kafka not available, using MockConsumer")
        return MockConsumer(**kwargs)
