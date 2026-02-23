import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

<<<<<<< Updated upstream
from apps.telemetry.models import Telemetry
from apps.telemetry.management.commands.mqtt_adapter import (
    handle_mqtt_message,
    _extract_serial_number,
=======
import pytest

from apps.telemetry.management.commands.mqtt_adapter import (
    Command,
    _build_mqtt_idempotency_key,
    _extract_serial_number,
    handle_mqtt_message,
>>>>>>> Stashed changes
)


class TestExtractSerialNumber:
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


<<<<<<< Updated upstream
@pytest.mark.django_db
class TestHandleMqttMessage:
    """Integration tests for the MQTT ingestion function."""

    def test_successful_ingestion(self, device):
=======
@pytest.fixture
def mock_producer():
    with patch("apps.telemetry.management.commands.mqtt_adapter.get_producer") as mock_get:
        producer = MagicMock()
        producer.publish_raw.return_value = "telemetry.raw"
        mock_get.return_value = producer
        yield producer


class TestMqttIdempotencyKey:
    def test_prefers_explicit_key(self):
        result = _build_mqtt_idempotency_key(
            topic="telemetry/SN1",
            serial_number="SN1",
            data={"idempotency_key": "  my-key  ", "seq": 10},
            payload_bytes=b'{"seq":10}',
        )
        assert result == "my-key"

    def test_is_stable_for_same_payload(self):
        payload = b'{"value":42}'
        first = _build_mqtt_idempotency_key(
            topic="telemetry/SN1",
            serial_number="SN1",
            data={"value": 42},
            payload_bytes=payload,
        )
        second = _build_mqtt_idempotency_key(
            topic="telemetry/SN1",
            serial_number="SN1",
            data={"value": 42},
            payload_bytes=payload,
        )
        assert first == second


class TestHandleMqttMessageKafkaMode:
    @pytest.fixture(autouse=True)
    def _kafka_mode(self, settings):
        settings.TELEMETRY_PIPELINE_MODE = "kafka"

    def test_valid_payload_accepted(self, mock_producer):
>>>>>>> Stashed changes
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 4250,
            }
        ).encode()

        result = handle_mqtt_message("telemetry/ignored", payload)

<<<<<<< Updated upstream
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
                "value": 1000,
            }
        ).encode()
=======
        assert result["status"] == "accepted"
        assert result["serial_number"] == "TEMP-SN-002"
        assert result["topic"] == "telemetry.raw"
        assert result["idempotency_key"].startswith("mqtt:")
        mock_producer.publish_raw.assert_called_once()

    def test_serial_number_from_topic(self, mock_producer):
        payload = json.dumps({"schema_version": "1.0", "value": 1000}).encode()
>>>>>>> Stashed changes

        result = handle_mqtt_message(f"telemetry/{device.serial_number}", payload)

<<<<<<< Updated upstream
        assert result["status"] == "created"
        assert Telemetry.objects.count() == 1

    def test_serial_number_in_body_takes_precedence(self, device):
        """serial_number in body is used even if topic has a different one."""
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "serial_number": device.serial_number,
                "value": 700,
=======
        assert result["status"] == "accepted"
        assert result["serial_number"] == "TEMP-SN-002"
        mock_producer.publish_raw.assert_called_once()

    def test_explicit_payload_idempotency_is_forwarded(self, mock_producer):
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "serial_number": "TEMP-SN-002",
                "idempotency_key": "  external-123 ",
>>>>>>> Stashed changes
            }
        ).encode()

        result = handle_mqtt_message("telemetry/TEMP-SN-002", payload)

<<<<<<< Updated upstream
        assert result["status"] == "created"
        assert Telemetry.objects.count() == 1
=======
        assert result["status"] == "accepted"
        call_kwargs = mock_producer.publish_raw.call_args.kwargs
        assert call_kwargs["data"]["idempotency_key"] == "external-123"

    def test_publish_raw_failure_returns_error(self, mock_producer):
        mock_producer.publish_raw.side_effect = RuntimeError("broker down")
        payload = json.dumps(
            {"schema_version": "1.0", "serial_number": "SN1", "value": 1000}
        ).encode()

        result = handle_mqtt_message("telemetry/SN1", payload)

        assert result["status"] == "error"
        assert result["reason"] == "publish_failed"
>>>>>>> Stashed changes

    def test_malformed_json(self):
        result = handle_mqtt_message("telemetry/SN1", b"not json{{{")

        assert result["status"] == "error"
        assert result["reason"] == "malformed_json"
        assert Telemetry.objects.count() == 0

<<<<<<< Updated upstream
    def test_empty_payload(self):
        result = handle_mqtt_message("telemetry/SN1", b"")

        assert result["status"] == "error"
        assert result["reason"] == "malformed_json"
        assert Telemetry.objects.count() == 0

=======
>>>>>>> Stashed changes
    def test_payload_is_list_not_dict(self):
        payload = json.dumps([{"schema_version": "1.0"}]).encode()

        result = handle_mqtt_message("telemetry/SN1", payload)

        assert result["status"] == "error"
        assert result["reason"] == "invalid_payload_type"

    def test_missing_serial_number_everywhere(self):
<<<<<<< Updated upstream
        """No serial_number in body and single-segment topic."""
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "value": 100,
            }
        ).encode()
=======
        payload = json.dumps({"schema_version": "1.0", "value": 100}).encode()
>>>>>>> Stashed changes

        result = handle_mqtt_message("telemetry", payload)

        assert result["status"] == "error"
        assert result["reason"] == "missing_serial_number"

    def test_nonexistent_device(self):
        payload = json.dumps(
            {
                "schema_version": "1.0",
                "serial_number": "DOES-NOT-EXIST",
                "value": 100,
            }
        ).encode()

<<<<<<< Updated upstream
        result = handle_mqtt_message("telemetry/DOES-NOT-EXIST", payload)

        assert result["status"] == "error"
        assert result["reason"] == "validation_failed"
        assert Telemetry.objects.count() == 0
=======
class TestHandleMqttMessageDirectMode:
    @pytest.fixture(autouse=True)
    def _direct_mode(self, settings):
        settings.TELEMETRY_PIPELINE_MODE = "direct"

    @patch("apps.telemetry.management.commands.mqtt_adapter.connection.ensure_connection")
    @patch("apps.telemetry.management.commands.mqtt_adapter.TelemetryValidator.validate_single")
    def test_validation_error(self, mock_validate_single, _mock_ensure_conn):
        mock_validate_single.return_value = (None, {"error": "Validation failed"})
        payload = json.dumps({"serial_number": "SN1", "value": "bad"}).encode()

        result = handle_mqtt_message("telemetry/SN1", payload)

        assert result["status"] == "error"
        assert result["reason"] == "validation_failed"

    @patch("apps.telemetry.management.commands.mqtt_adapter.connection.ensure_connection")
    @patch("apps.telemetry.management.commands.mqtt_adapter.TelemetryBatchProcessor.process_single")
    @patch("apps.telemetry.management.commands.mqtt_adapter.TelemetryValidator.validate_single")
    def test_persists_and_returns_created(
        self,
        mock_validate_single,
        mock_process_single,
        _mock_ensure_conn,
    ):
        mock_validate_single.return_value = (
            {"device": SimpleNamespace(id="dev-1"), "payload": {"value": 12}},
            None,
        )
        mock_process_single.return_value = SimpleNamespace(id=10, device_id="dev-1")
        payload = json.dumps({"serial_number": "SN1", "value": 12}).encode()

        result = handle_mqtt_message("telemetry/SN1", payload)

        assert result["status"] == "created"
        assert result["serial_number"] == "SN1"
        assert result["telemetry_id"] == 10
        assert result["device_id"] == "dev-1"


class TestHandleDeviceStatus:
    def test_online_status(self, caplog):
        with caplog.at_level("INFO"):
            Command._handle_device_status("devices/TEMP-SN-002/status", b"online")
        assert "Device status change" in caplog.text
>>>>>>> Stashed changes

    def test_invalid_schema_version(self, device):
        payload = json.dumps(
            {
                "schema_version": "999.0",
                "serial_number": device.serial_number,
                "value": 100,
            }
        ).encode()

        result = handle_mqtt_message(f"telemetry/{device.serial_number}", payload)

<<<<<<< Updated upstream
        assert result["status"] == "error"
        assert result["reason"] == "validation_failed"
        assert Telemetry.objects.count() == 0

    def test_missing_schema_version(self, device):
        payload = json.dumps(
            {
                "serial_number": device.serial_number,
                "value": 100,
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
                "value": 500,
            }
        ).encode()

        with patch(
            "apps.telemetry.management.commands.mqtt_adapter.TelemetryBatchProcessor"
        ) as mock_proc:
            mock_proc.process_single.side_effect = Exception("DB down")
            result = handle_mqtt_message(f"telemetry/{device.serial_number}", payload)

        assert result["status"] == "error"
        assert result["reason"] == "persistence_failed"
=======
    def test_short_topic_ignored(self):
        Command._handle_device_status("devices", b"online")
>>>>>>> Stashed changes


@pytest.mark.django_db
class TestMqttAdapterCommandCallbacks:
    @patch("apps.telemetry.management.commands.mqtt_adapter.mqtt.Client")
<<<<<<< Updated upstream
    def test_on_message_calls_handle(self, MockClient, device):
        """Simulate paho delivering a message and verify ingestion runs."""
        from apps.telemetry.management.commands.mqtt_adapter import Command

=======
    def test_on_message_calls_handle(self, mock_client_cls):
>>>>>>> Stashed changes
        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.stderr = MagicMock()

        mock_client_instance = mock_client_cls.return_value
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

        assert "on_connect" in callbacks
        assert "on_message" in callbacks
        assert "on_disconnect" in callbacks

<<<<<<< Updated upstream
        # Simulate on_connect
        callbacks["on_connect"](mock_client_instance, None, None, 0, None)
        mock_client_instance.subscribe.assert_called_once_with("telemetry/#", qos=1)

        # Simulate on_message with a real payload
=======
        callbacks["on_connect"](mock_client_instance, None, None, 0, None)
        assert mock_client_instance.subscribe.call_count == 2

>>>>>>> Stashed changes
        msg = MagicMock()
        msg.topic = f"telemetry/{device.serial_number}"
        msg.payload = json.dumps(
            {
                "schema_version": "1.0",
                "value": 999,
            }
        ).encode()

        with patch(
            "apps.telemetry.management.commands.mqtt_adapter.handle_mqtt_message"
        ) as mock_handle:
            mock_handle.return_value = {"status": "created"}
            callbacks["on_message"](mock_client_instance, None, msg)
            mock_handle.assert_called_once_with(msg.topic, msg.payload)
<<<<<<< Updated upstream
=======

    @patch("apps.telemetry.management.commands.mqtt_adapter.mqtt.Client")
    def test_device_status_message_bypasses_telemetry_handler(self, mock_client_cls):
        cmd = Command()
        cmd.stdout = MagicMock()
        cmd.stderr = MagicMock()

        mock_client_instance = mock_client_cls.return_value
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
>>>>>>> Stashed changes
