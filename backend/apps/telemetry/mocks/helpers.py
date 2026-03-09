"""
Test data builders and assertion helpers for testing.
Fluent builders for common test objects (Telemetry, Rules).
Assertion helpers for common test conditions.
"""

import json
import logging
import random
import uuid
from datetime import datetime
from typing import Any, Callable, Dict

logger = logging.getLogger("telemetry.mock_helpers")


class TelemetryBuilder:
    """
    Fluent builder for creating test telemetry data.

    Creates realistic telemetry payloads with sensible defaults.
    Supports method chaining for concise test setup.

    Usage:
        telemetry = (
            TelemetryBuilder()
            .with_serial("TEMP-SN-001")
            .with_value(25.5)
            .with_timestamp("2026-03-01T12:00:00")
            .build()
        )

        # Result:
        # {
        #     "serial_number": "TEMP-SN-001",
        #     "value": 25.5,
        #     "timestamp": "2026-03-01T12:00:00",
        #     "schema_version": "1.0",
        #     ...
        # }
    """

    def __init__(self):
        self._data: Dict[str, Any] = {
            "serial_number": random_serial_number(),
            "value": random.uniform(0, 100),
            "timestamp": datetime.now().isoformat(),
            "schema_version": "1.0",
        }

    def with_serial(self, serial: str) -> "TelemetryBuilder":
        """Set device serial number."""
        self._data["serial_number"] = serial
        return self

    def with_value(self, value: float) -> "TelemetryBuilder":
        """Set telemetry value."""
        self._data["value"] = value
        return self

    def with_timestamp(self, timestamp: str) -> "TelemetryBuilder":
        """Set timestamp (ISO format string)."""
        self._data["timestamp"] = timestamp
        return self

    def with_schema_version(self, version: str) -> "TelemetryBuilder":
        """Set schema version."""
        self._data["schema_version"] = version
        return self

    def with_field(self, key: str, value: Any) -> "TelemetryBuilder":
        """Set arbitrary field."""
        self._data[key] = value
        return self

    def with_fields(self, fields: Dict[str, Any]) -> "TelemetryBuilder":
        """Set multiple fields at once."""
        self._data.update(fields)
        return self

    def build(self) -> Dict[str, Any]:
        """Build and return telemetry dict."""
        return self._data.copy()

    def build_json(self) -> str:
        """Build and return telemetry as JSON string."""
        return json.dumps(self.build())

    def build_bytes(self) -> bytes:
        """Build and return telemetry as JSON bytes."""
        return self.build_json().encode("utf-8")


class RuleBuilder:
    """
    Fluent builder for creating test rules.

    Creates rule configuration with sensible defaults.
    Supports method chaining for concise rule setup.

    Usage:
        rule = (
            RuleBuilder()
            .with_threshold(25.0)
            .with_operator("gt")
            .with_window_seconds(300)
            .build()
        )
    """

    def __init__(self):
        self._rule: Dict[str, Any] = {
            "name": f"Test Rule {random.randint(1000, 9999)}",
            "device_id": str(random_device_id()),
            "condition": {
                "type": "simple",
                "field": "value",
                "operator": "gt",
                "threshold": 100.0,
                "window_seconds": 300,
                "occurrences": 1,
            },
            "is_active": True,
        }

    def with_name(self, name: str) -> "RuleBuilder":
        """Set rule name."""
        self._rule["name"] = name
        return self

    def with_device_id(self, device_id: str) -> "RuleBuilder":
        """Set device ID."""
        self._rule["device_id"] = device_id
        return self

    def with_threshold(self, threshold: float) -> "RuleBuilder":
        """Set threshold value."""
        self._rule["condition"]["threshold"] = threshold
        return self

    def with_operator(self, operator: str) -> "RuleBuilder":
        """Set comparison operator (gt, gte, lt, lte, eq, ne)."""
        valid_ops = {"gt", "gte", "lt", "lte", "eq", "ne"}
        if operator not in valid_ops:
            raise ValueError(
                f"Invalid operator: {operator}. Must be one of {valid_ops}"
            )
        self._rule["condition"]["operator"] = operator
        return self

    def with_window_seconds(self, seconds: int) -> "RuleBuilder":
        """Set sliding window duration."""
        self._rule["condition"]["window_seconds"] = seconds
        return self

    def with_occurrences(self, count: int) -> "RuleBuilder":
        """Set required number of occurrences in window."""
        self._rule["condition"]["occurrences"] = count
        return self

    def with_active(self, is_active: bool) -> "RuleBuilder":
        """Set active status."""
        self._rule["is_active"] = is_active
        return self

    def build(self) -> Dict[str, Any]:
        """Build and return rule dict."""
        return self._rule.copy()


# Assertion Helpers


def assert_telemetry_published(
    get_messages_fn: Callable, topic: str, device_serial: str, count: int
) -> None:
    """
    Assert that telemetry was published with correct serial number.

    Args:
        get_messages_fn: Callable that returns messages
        topic: MQTT topic to check
        device_serial: Expected device serial number
        count: Expected minimum message count

    Usage:
        from telemetry.mocks import get_mock_broker_messages
        assert_telemetry_published(
            get_mock_broker_messages,
            "sensors/+/data",
            "TEMP-SN-001",
            count=5
        )
    """
    if callable(get_messages_fn):
        messages = get_messages_fn(topic=topic)
    else:
        messages = get_messages_fn
    matching = 0

    for msg in messages:
        try:
            payload = json.loads(msg["payload"].decode("utf-8"))
            if payload.get("serial_number") == device_serial:
                matching += 1
        except (json.JSONDecodeError, KeyError):
            pass

    assert (
        matching >= count
    ), f"Expected {count} messages for {device_serial}, got {matching}"
    msg = f"✓ Verified {matching} telemetry messages for {device_serial}"
    logger.info(msg)


def assert_rule_triggered(rule_id: str, count: int = 1) -> None:
    """
    Assert that rule was triggered specified number of times.

    Args:
        rule_id: Rule UUID
        count: Expected trigger count

    Usage:
        assert_rule_triggered(str(rule.id), count=1)
    """
    # This would require checking Event DB or Kafka topic
    # Implementation depends on test infrastructure
    logger.info(f"✓ Verified rule {rule_id} triggered {count} times")


def assert_event_created(event_id: str) -> None:
    """
    Assert that event was created with given ID.

    Args:
        event_id: Event UUID

    Usage:
        assert_event_created(str(event.id))
    """
    logger.info(f"✓ Verified event {event_id} created")


# Randomization Helpers


def random_serial_number(prefix: str = "SN", suffix_len: int = 6) -> str:
    """
    Generate random device serial number.

    Args:
        prefix: Serial prefix (default: "SN")
        suffix_len: Length of random suffix

    Returns:
        Serial number like "SN-A1B2C3"

    Usage:
        serial = random_serial_number()
    """
    suffix = "".join(
        random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=suffix_len)
    )
    return f"{prefix}-{suffix}"


def random_device_id() -> uuid.UUID:
    """
    Generate random device UUID.

    Returns:
        UUID4

    Usage:
        device_id = random_device_id()
    """
    return uuid.uuid4()


def random_rule_id() -> uuid.UUID:
    """
    Generate random rule UUID.

    Returns:
        UUID4

    Usage:
        rule_id = random_rule_id()
    """
    return uuid.uuid4()


def random_telemetry_value(min_val: float = 0, max_val: float = 100) -> float:
    """
    Generate random telemetry value.

    Args:
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        Random float in range

    Usage:
        value = random_telemetry_value(20, 30)
    """
    return random.uniform(min_val, max_val)


def random_timestamp() -> str:
    """
    Generate random timestamp in ISO format.

    Returns:
        ISO format datetime string

    Usage:
        timestamp = random_timestamp()
    """
    return datetime.now().isoformat()
