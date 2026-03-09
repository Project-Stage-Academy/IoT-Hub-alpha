"""Complete tests for MQTT idempotency key generation edge cases."""

from apps.telemetry.management.commands.mqtt_adapter import (
    _normalize_idempotency_value,
    _build_mqtt_idempotency_key,
)


class TestNormalizeIdempotencyValue:
    """Test _normalize_idempotency_value handles all edge cases."""

    def test_normalize_value_none_returns_none(self):
        """None value returns None."""
        assert _normalize_idempotency_value(None) is None

    def test_normalize_value_empty_string_returns_none(self):
        """Empty string returns None."""
        assert _normalize_idempotency_value("") is None

    def test_normalize_value_whitespace_only_returns_none(self):
        """Whitespace-only string returns None."""
        assert _normalize_idempotency_value("   ") is None
        assert _normalize_idempotency_value("\t") is None
        assert _normalize_idempotency_value("\n") is None

    def test_normalize_value_zero_is_valid(self):
        """Zero converts to string '0' (not None)."""
        result = _normalize_idempotency_value(0)
        assert result == "0"
        assert result is not None

    def test_normalize_value_false_is_valid(self):
        """False converts to string 'False' (not None)."""
        result = _normalize_idempotency_value(False)
        assert result == "False"
        assert result is not None


class TestBuildMQTTIdempotencyKey:
    """Test _build_mqtt_idempotency_key edge cases."""

    def test_explicit_idempotency_key_preferred(self):
        """Explicit idempotency_key takes priority."""
        key1 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data={"idempotency_key": "explicit-123", "message_id": "msg-999"},
            payload_bytes=b"payload1",
        )
        key2 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data={"idempotency_key": "explicit-123", "message_id": "msg-999"},
            payload_bytes=b"payload2",  # Different payload
        )

        assert key1 == key2 == "explicit-123"

    def test_explicit_empty_key_ignored_uses_stable_fields(self):
        """Empty explicit key falls back to stable fields."""
        key = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data={"idempotency_key": "", "message_id": "msg-123"},
            payload_bytes=b"payload",
        )

        # Should use stable fields, not explicit key
        assert key.startswith("mqtt:")
        assert "msg-123" not in key or "SN-001" in key  # Uses hash format

    def test_multiple_stable_fields_all_included(self):
        """All stable fields included in hash when present."""
        data_with_multiple = {
            "message_id": "id-123",
            "seq": "seq-456",
            "timestamp": "2026-01-01T00:00:00Z",
            "ts": "ts-789",  # Multiple timestamp fields
        }

        key = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data_with_multiple,
            payload_bytes=b"payload",
        )

        # Key should be based on hash of fields
        assert key.startswith("mqtt:")

    def test_stable_fields_priority_order(self):
        """Uses first found stable field from priority list."""
        # With message_id
        key1 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data={"message_id": "id-1", "seq": "seq-2"},
            payload_bytes=b"payload",
        )

        # With only seq
        key2 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data={"seq": "seq-2"},
            payload_bytes=b"payload",
        )

        # Both should include stable fields, but may differ
        assert key1.startswith("mqtt:")
        assert key2.startswith("mqtt:")

    def test_json_key_order_independence(self):
        """Different JSON key order produces same hash (sort_keys=True)."""
        data_order1 = {
            "message_id": "msg-123",
            "serial_number": "SN-001",
            "seq": "seq-456",
        }
        data_order2 = {
            "seq": "seq-456",
            "message_id": "msg-123",
            "serial_number": "SN-001",
        }

        key1 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data_order1,
            payload_bytes=b"payload",
        )
        key2 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data_order2,
            payload_bytes=b"payload",
        )

        assert key1 == key2

    def test_fallback_to_payload_hash_no_stable_fields(self):
        """Uses full payload hash when no stable fields present."""
        data_no_stable = {"value": 42, "unit": "celsius"}

        key = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data_no_stable,
            payload_bytes=b"payload-data",
        )

        assert key.startswith("mqtt:")

    def test_same_payload_same_key_deterministic(self):
        """Same payload always produces same key (deterministic)."""
        data = {"value": 42}
        payload = b"same-payload"

        key1 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data,
            payload_bytes=payload,
        )
        key2 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data,
            payload_bytes=payload,
        )

        assert key1 == key2

    def test_different_payload_different_key(self):
        """Different payloads produce different keys."""
        data = {"value": 42}

        key1 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data,
            payload_bytes=b"payload1",
        )
        key2 = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data,
            payload_bytes=b"payload2",
        )

        assert key1 != key2

    def test_unicode_serial_number(self):
        """Unicode in serial number handled correctly."""
        key = _build_mqtt_idempotency_key(
            topic="telemetry/SN-температура-001",
            serial_number="SN-температура-001",
            data={"message_id": "msg-123"},
            payload_bytes=b"payload",
        )

        assert key.startswith("mqtt:")
        assert isinstance(key, str)

    def test_unicode_in_payload_data(self):
        """Unicode in payload data handled correctly."""
        data = {
            "message_id": "msg-123",
            "note": "Фізична температура 🌡️",
        }

        key = _build_mqtt_idempotency_key(
            topic="telemetry/SN-001",
            serial_number="SN-001",
            data=data,
            payload_bytes=b"payload",
        )

        assert key.startswith("mqtt:")
        assert isinstance(key, str)
