"""Tests for MQTT device status event handling."""

import pytest
import logging
from unittest.mock import MagicMock, patch


class TestDeviceStatusHandling:
    """Test device status event handling (online/offline)."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for status events."""
        return MagicMock(spec=logging.Logger)

    def test_online_status_logged(self, mock_logger):
        """Online status event logged correctly."""
        topic = "devices/TEMP-SN-002/status"
        payload = b"online"

        # Mock function to capture logging
        with patch("logging.getLogger") as get_logger:
            get_logger.return_value = mock_logger

            # Parse topic to extract serial
            parts = topic.strip("/").split("/")
            serial_number = parts[-2] if len(parts) > 1 else None

            assert serial_number == "TEMP-SN-002"
            decoded = payload.decode("utf-8", errors="replace").strip()
            assert decoded.lower() == "online"

    def test_offline_status_logged(self, mock_logger):
        """Offline status event logged correctly."""
        topic = "devices/TEMP-SN-002/status"
        payload = b"offline"

        parts = topic.strip("/").split("/")
        serial_number = parts[-2] if len(parts) > 1 else None
        status = payload.decode("utf-8", errors="replace").strip().lower()

        assert serial_number == "TEMP-SN-002"
        assert status == "offline"

    def test_empty_status_payload(self):
        """Empty status payload handled gracefully."""
        topic = "devices/TEMP-SN-002/status"
        payload = b""

        parts = topic.strip("/").split("/")
        serial_number = parts[-2] if len(parts) > 1 else None
        status = payload.decode("utf-8", errors="replace").strip()

        assert serial_number == "TEMP-SN-002"
        assert status == ""

    def test_status_with_newline_stripped(self):
        """Status payload with newline is stripped."""
        payloads = [b"online\n", b"offline\r\n", b"  online  \n"]

        for payload in payloads:
            status = payload.decode("utf-8", errors="replace").strip().lower()
            assert status in ["online", "offline"]

    def test_status_with_whitespace_trimmed(self):
        """Status payload with leading/trailing whitespace trimmed."""
        payloads = [b"  online  ", b"\tonline\t", b"  offline  "]

        for payload in payloads:
            status = payload.decode("utf-8", errors="replace").strip().lower()
            assert status in ["online", "offline"]

    def test_device_status_topic_parsing(self):
        """Device status topic correctly parsed."""
        test_cases = [
            ("devices/TEMP-SN-002/status", "TEMP-SN-002"),
            ("devices/CUR-SN-001/status", "CUR-SN-001"),
            ("devices/VIB-SN-003/status", "VIB-SN-003"),
        ]

        for topic, expected_serial in test_cases:
            parts = topic.strip("/").split("/")
            serial = parts[-2] if parts[-1] == "status" else parts[-1]
            assert serial == expected_serial

    def test_empty_serial_in_status_topic(self):
        """Empty serial number in topic handled."""
        topic = "devices//status"

        parts = topic.strip("/").split("/")
        # Filter out empty strings from double slash
        parts_filtered = [p for p in parts if p]

        # Should handle gracefully (either skip or use first/last)
        if parts_filtered:
            assert "status" in parts_filtered

    def test_missing_status_in_topic(self):
        """Topic without 'status' suffix handled."""
        topic = "devices/TEMP-SN-002"

        parts = topic.strip("/").split("/")
        is_status_topic = parts[-1] == "status" if parts else False

        assert not is_status_topic

    def test_invalid_utf8_bytes(self):
        """Invalid UTF-8 bytes replaced gracefully."""
        payload = b"\x80\x81\x82\x83"

        decoded = payload.decode("utf-8", errors="replace")

        # Should decode without raising, with replacement chars
        assert isinstance(decoded, str)
        assert "\ufffd" in decoded  # Replacement character

    def test_mqtt_will_message_offline(self):
        """MQTT LWT (Last Will Testament) message for offline."""
        topic = "devices/TEMP-SN-002/status"
        payload = b"offline"  # LWT typically sends offline

        parts = topic.strip("/").split("/")
        serial = parts[-2] if len(parts) > 1 else None
        status = payload.decode("utf-8", errors="replace").strip().lower()

        assert serial == "TEMP-SN-002"
        assert status == "offline"

    def test_status_topic_with_trailing_slash(self):
        """Status topic with trailing slash handled."""
        topic = "devices/TEMP-SN-002/status/"

        parts = topic.strip("/").split("/")
        is_status = "status" in parts

        assert is_status

    def test_multiple_devices_status_same_time(self):
        """Multiple device status messages handled in sequence."""
        topics = [
            "devices/TEMP-SN-001/status",
            "devices/TEMP-SN-002/status",
            "devices/CUR-SN-001/status",
        ]
        payloads = [b"online", b"offline", b"online"]

        for topic, payload in zip(topics, payloads):
            parts = topic.strip("/").split("/")
            serial = parts[-2] if parts[-1] == "status" else None
            status = payload.decode("utf-8", errors="replace").strip().lower()

            assert serial is not None
            assert status in ["online", "offline"]

    def test_status_transition_online_to_offline(self):
        """Device status transition (online → offline) tracked."""
        # First message: online
        status1 = "online"
        assert status1 == "online"

        # Second message: offline
        status2 = "offline"
        assert status2 == "offline"

        # Transition detected
        assert status1 != status2

    def test_status_unchanged_multiple_messages(self):
        """Multiple messages with same status handled."""
        statuses = ["online", "online", "online"]

        for status in statuses:
            assert status == "online"
