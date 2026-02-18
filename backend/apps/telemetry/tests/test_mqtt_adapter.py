import json
import pytest
from unittest.mock import MagicMock, patch

from apps.telemetry.management.commands.mqtt_adapter import (
    handle_mqtt_message,
    _extract_serial_number,
    Command,
    DEVICE_STATUS_TOPIC,
)


class TestExtractSerialNumber:
    """Unit tests for topic parsing."""

    def test_standard_topic(self):
        assert _extract_serial_number("telemetry/TEMP-SN-002") == "TEMP-SN-002"

    def test_trailing_slash_topic(self):
        assert _extract_serial_number("telemetry/TEMP-SN-002/") == "TEMP-SN-002"

    def test_deep_topic(self):
        assert _extract_serial_number("v1/telemetry/TEMP-SN-002") == "TEMP-SN-002"

    def test_single_segment_topic(self):
        assert _extract_serial_number("telemetry") is None

    def test_empty_topic(self):
        assert _extract_serial_number("") is None


@pytest.fixture(autouse=True)
def _mock_producer():
    """Patch the producer so publish_raw is a no-op in all tests."""
    with patch(
        "apps.telemetry.management.commands.mqtt_adapter.get_producer"
    ) as mock_get:
        mock_get.return_value = MagicMock()
        yield mock_get.return_value


class TestHandleMqttMessage:
    """Tests for the publish-only MQTT ingestion function."""

    def test_valid_payload_accepted(self, _mock_producer):
        payload = json.dumps(
            {"schema_version": "1.0", "serial_number": "TEMP-SN-002", "value": 4250}
        ).encode()

        result = handle_mqtt_message("telemetry/ignored", payload)

        assert result["status"] == "accepted"
        assert result["serial_number"] == "TEMP-SN-002"
        _mock_producer.publish_raw.assert_called_once()

    def test_serial_number_from_topic(self, _mock_producer):
        """serial_number missing in body -> extracted from topic."""
        payload = json.dumps({"schema_version": "1.0", "value": 1000}).encode()

        result = handle_mqtt_message("telemetry/TEMP-SN-002", payload)

        assert result["status"] == "accepted"
        assert result["serial_number"] == "TEMP-SN-002"
        _mock_producer.publish_raw.assert_called_once()

    def test_serial_number_in_body_takes_precedence(self, _mock_producer):
        """serial_number in body is used even if topic has a different one."""
        payload = json.dumps(
            {"schema_version": "1.0", "serial_number": "FROM-BODY", "value": 700}
        ).encode()

        result = handle_mqtt_message("telemetry/OTHER-SN", payload)

        assert result["status"] == "accepted"
        assert result["serial_number"] == "FROM-BODY"

    def test_publish_raw_called_with_correct_source(self, _mock_producer):
        payload = json.dumps(
            {"schema_version": "1.0", "serial_number": "SN1", "value": 1}
        ).encode()

        handle_mqtt_message("telemetry/SN1", payload)

        call_kwargs = _mock_producer.publish_raw.call_args.kwargs
        assert call_kwargs["source"] == "mqtt"
        assert call_kwargs["serial_number"] == "SN1"

    def test_publish_raw_failure_returns_error(self, _mock_producer):
        """If producer fails, return error (no DB fallback)."""
        _mock_producer.publish_raw.side_effect = RuntimeError("broker down")
        payload = json.dumps(
            {"schema_version": "1.0", "serial_number": "SN1", "value": 1000}
        ).encode()

        result = handle_mqtt_message("telemetry/SN1", payload)

        assert result["status"] == "error"
        assert result["reason"] == "publish_failed"

    # Error scenarios

    def test_malformed_json(self):
        result = handle_mqtt_message("telemetry/SN1", b"not json{{{")

        assert result["status"] == "error"
        assert result["reason"] == "malformed_json"

    def test_empty_payload(self):
        result = handle_mqtt_message("telemetry/SN1", b"")

        assert result["status"] == "error"
        assert result["reason"] == "malformed_json"

    def test_payload_is_list_not_dict(self):
        payload = json.dumps([{"schema_version": "1.0"}]).encode()

        result = handle_mqtt_message("telemetry/SN1", payload)

        assert result["status"] == "error"
        assert result["reason"] == "invalid_payload_type"

    def test_missing_serial_number_everywhere(self):
        """No serial_number in body and single-segment topic."""
        payload = json.dumps({"schema_version": "1.0", "value": 100}).encode()

        result = handle_mqtt_message("telemetry", payload)

        assert result["status"] == "error"
        assert result["reason"] == "missing_serial_number"


class TestHandleDeviceStatus:
    """Unit tests for device connection/disconnect event handling."""

    def test_online_status(self, caplog):
        with caplog.at_level("INFO"):
            Command._handle_device_status("devices/TEMP-SN-002/status", b"online")
        assert "Device status change" in caplog.text

    def test_offline_status(self, caplog):
        with caplog.at_level("INFO"):
            Command._handle_device_status("devices/TEMP-SN-002/status", b"offline")
        assert "Device status change" in caplog.text

    def test_extracts_serial_from_topic(self, caplog):
        with caplog.at_level("INFO"):
            Command._handle_device_status("devices/HUM-SN-001/status", b"online")
        record = caplog.records[-1]
        assert record.serial_number == "HUM-SN-001"

    def test_short_topic_ignored(self):
        # Should not raise
        Command._handle_device_status("devices", b"online")


class TestMqttAdapterCommandCallbacks:
    """Test that the management command wires paho callbacks correctly."""

    @patch("apps.telemetry.management.commands.mqtt_adapter.mqtt.Client")
    def test_on_message_calls_handle(self, MockClient):
        """Simulate paho delivering a message and verify ingestion runs."""
        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.stderr = MagicMock()

        mock_client_instance = MockClient.return_value
        mock_client_instance.connect.return_value = 0

        callbacks = {}

        def capture_on_connect(cb):
            callbacks["on_connect"] = cb

        def capture_on_message(cb):
            callbacks["on_message"] = cb

        def capture_on_disconnect(cb):
            callbacks["on_disconnect"] = cb

        type(mock_client_instance).on_connect = property(
            fget=lambda self: callbacks.get("on_connect"),
            fset=lambda self, v: capture_on_connect(v),
        )
        type(mock_client_instance).on_message = property(
            fget=lambda self: callbacks.get("on_message"),
            fset=lambda self, v: capture_on_message(v),
        )
        type(mock_client_instance).on_disconnect = property(
            fget=lambda self: callbacks.get("on_disconnect"),
            fset=lambda self, v: capture_on_disconnect(v),
        )

        mock_client_instance.loop_forever.side_effect = KeyboardInterrupt

        try:
            cmd.handle(host="localhost", port=1883, topic="telemetry/#", qos=1)
        except (KeyboardInterrupt, SystemExit):
            pass

        # Verify callbacks were wired
        assert "on_connect" in callbacks
        assert "on_message" in callbacks
        assert "on_disconnect" in callbacks

        # Simulate on_connect — subscribes to telemetry AND device status
        callbacks["on_connect"](mock_client_instance, None, None, 0, None)
        assert mock_client_instance.subscribe.call_count == 2
        subscribe_calls = [
            c.args for c in mock_client_instance.subscribe.call_args_list
        ]
        assert ("telemetry/#",) in [c[:1] for c in subscribe_calls]

        # Simulate on_message with a telemetry payload
        msg = MagicMock()
        msg.topic = "telemetry/TEMP-SN-002"
        msg.payload = json.dumps({"schema_version": "1.0", "value": 999}).encode()

        with patch(
            "apps.telemetry.management.commands.mqtt_adapter.handle_mqtt_message"
        ) as mock_handle:
            mock_handle.return_value = {"status": "accepted"}
            callbacks["on_message"](mock_client_instance, None, msg)
            mock_handle.assert_called_once_with(msg.topic, msg.payload)

    @patch("apps.telemetry.management.commands.mqtt_adapter.mqtt.Client")
    def test_device_status_message_routed_correctly(self, MockClient):
        """Device status messages must NOT reach handle_mqtt_message."""
        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.stderr = MagicMock()

        mock_client_instance = MockClient.return_value
        mock_client_instance.connect.return_value = 0

        callbacks = {}

        type(mock_client_instance).on_connect = property(
            fget=lambda self: callbacks.get("on_connect"),
            fset=lambda self, v: callbacks.__setitem__("on_connect", v),
        )
        type(mock_client_instance).on_message = property(
            fget=lambda self: callbacks.get("on_message"),
            fset=lambda self, v: callbacks.__setitem__("on_message", v),
        )
        type(mock_client_instance).on_disconnect = property(
            fget=lambda self: callbacks.get("on_disconnect"),
            fset=lambda self, v: callbacks.__setitem__("on_disconnect", v),
        )

        mock_client_instance.loop_forever.side_effect = KeyboardInterrupt

        try:
            cmd.handle(host="localhost", port=1883, topic="telemetry/#", qos=1)
        except (KeyboardInterrupt, SystemExit):
            pass

        msg = MagicMock()
        msg.topic = "devices/TEMP-SN-002/status"
        msg.payload = b"online"

        with patch(
            "apps.telemetry.management.commands.mqtt_adapter.handle_mqtt_message"
        ) as mock_handle:
            callbacks["on_message"](mock_client_instance, None, msg)
            mock_handle.assert_not_called()
