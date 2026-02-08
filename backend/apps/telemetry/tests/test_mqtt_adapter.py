import json
import pytest
from unittest.mock import MagicMock, patch

from apps.telemetry.models import Telemetry
from apps.telemetry.management.commands.mqtt_adapter import (
    handle_mqtt_message,
    _extract_serial_number,
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


@pytest.mark.django_db
class TestHandleMqttMessage:
    """Integration tests for the MQTT ingestion function."""

    def test_successful_ingestion(self, device):
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 42.5,
            }
        ).encode()

        result = handle_mqtt_message("telemetry/ignored", payload)

        assert result["status"] == "created"
        assert "telemetry_id" in result
        assert result["device_id"] == str(device.id)
        assert Telemetry.objects.count() == 1
        t = Telemetry.objects.first()
        assert t.device == device
        assert t.payload["value"] == 42.5

    def test_serial_number_from_topic(self, device):
        """serial_number missing in body → extracted from topic."""
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "value": 10.0,
            }
        ).encode()

        result = handle_mqtt_message(f"telemetry/{device.serial_number}", payload)

        assert result["status"] == "created"
        assert Telemetry.objects.count() == 1

    def test_serial_number_in_body_takes_precedence(self, device):
        """serial_number in body is used even if topic has a different one."""
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 7.0,
            }
        ).encode()

        result = handle_mqtt_message("telemetry/OTHER-SN", payload)

        assert result["status"] == "created"
        assert Telemetry.objects.count() == 1

    # Error scenarios

    def test_malformed_json(self):
        result = handle_mqtt_message("telemetry/SN1", b"not json{{{")

        assert result["status"] == "error"
        assert result["reason"] == "malformed_json"
        assert Telemetry.objects.count() == 0

    def test_empty_payload(self):
        result = handle_mqtt_message("telemetry/SN1", b"")

        assert result["status"] == "error"
        assert result["reason"] == "malformed_json"
        assert Telemetry.objects.count() == 0

    def test_payload_is_list_not_dict(self):
        payload = json.dumps([{"schema_version": "1.0"}]).encode()

        result = handle_mqtt_message("telemetry/SN1", payload)

        assert result["status"] == "error"
        assert result["reason"] == "invalid_payload_type"

    def test_missing_serial_number_everywhere(self):
        """No serial_number in body and single-segment topic."""
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "value": 1.0,
            }
        ).encode()

        result = handle_mqtt_message("telemetry", payload)

        assert result["status"] == "error"
        assert result["reason"] == "missing_serial_number"

    def test_nonexistent_device(self):
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "serial_number": "DOES-NOT-EXIST",
                "value": 1.0,
            }
        ).encode()

        result = handle_mqtt_message("telemetry/DOES-NOT-EXIST", payload)

        assert result["status"] == "error"
        assert result["reason"] == "validation_failed"
        assert Telemetry.objects.count() == 0

    def test_invalid_schema_version(self, device):
        payload = json.dumps(
            {
                "schema_version": "999.0",
                "serial_number": device.serial_number,
                "value": 1.0,
            }
        ).encode()

        result = handle_mqtt_message(f"telemetry/{device.serial_number}", payload)

        assert result["status"] == "error"
        assert result["reason"] == "validation_failed"
        assert Telemetry.objects.count() == 0

    def test_missing_schema_version(self, device):
        payload = json.dumps(
            {
                "serial_number": device.serial_number,
                "value": 1.0,
            }
        ).encode()

        result = handle_mqtt_message(f"telemetry/{device.serial_number}", payload)

        assert result["status"] == "error"
        assert result["reason"] == "validation_failed"

    def test_persistence_error_is_caught(self, device):
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 5.0,
            }
        ).encode()

        with patch(
            "apps.telemetry.management.commands.mqtt_adapter.TelemetryBatchProcessor"
        ) as mock_proc:
            mock_proc.process_single.side_effect = Exception("DB down")
            result = handle_mqtt_message(f"telemetry/{device.serial_number}", payload)

        assert result["status"] == "error"
        assert result["reason"] == "persistence_failed"


@pytest.mark.django_db
class TestMqttAdapterCommandCallbacks:
    """Test that the management command wires paho callbacks correctly."""

    @patch("apps.telemetry.management.commands.mqtt_adapter.mqtt.Client")
    def test_on_message_calls_handle(self, MockClient, device):
        """Simulate paho delivering a message and verify ingestion runs."""
        from apps.telemetry.management.commands.mqtt_adapter import Command

        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.stderr = MagicMock()

        mock_client_instance = MockClient.return_value
        mock_client_instance.connect.return_value = 0

        # Capture the on_message callback assigned during handle()
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

        # Make loop_forever exit immediately
        mock_client_instance.loop_forever.side_effect = KeyboardInterrupt

        try:
            cmd.handle(host="localhost", port=1883, topic="telemetry/#", qos=1)
        except (KeyboardInterrupt, SystemExit):
            pass

        # Verify callbacks were wired
        assert "on_connect" in callbacks
        assert "on_message" in callbacks
        assert "on_disconnect" in callbacks

        # Simulate on_connect
        callbacks["on_connect"](mock_client_instance, None, None, 0, None)
        mock_client_instance.subscribe.assert_called_once_with("telemetry/#", qos=1)

        # Simulate on_message with a real payload
        msg = MagicMock()
        msg.topic = f"telemetry/{device.serial_number}"
        msg.payload = json.dumps(
            {
                "schema_version": "1.0",
                "value": 99.9,
            }
        ).encode()

        with patch(
            "apps.telemetry.management.commands.mqtt_adapter.handle_mqtt_message"
        ) as mock_handle:
            mock_handle.return_value = {"status": "created"}
            callbacks["on_message"](mock_client_instance, None, msg)
            mock_handle.assert_called_once_with(msg.topic, msg.payload)
