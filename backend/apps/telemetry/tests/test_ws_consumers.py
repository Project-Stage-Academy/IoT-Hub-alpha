import json
import pytest
from unittest.mock import AsyncMock

from apps.telemetry.consumers import (
    TelemetryConsumer,
    broadcast_telemetry,
    connected_clients,
)


class TestTelemetryConsumerSubscriptions:
    """Tests for TelemetryConsumer subscription logic."""

    def setup_method(self):
        """Clear connected_clients before each test."""
        connected_clients.clear()

    def test_is_subscribed_to_empty(self):
        """Test is_subscribed_to returns False when no subscriptions."""
        consumer = TelemetryConsumer()
        assert consumer.is_subscribed_to("DEVICE-001") is False

    def test_is_subscribed_to_subscribed_device(self):
        """Test is_subscribed_to returns True for subscribed device."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.add("DEVICE-001")
        assert consumer.is_subscribed_to("DEVICE-001") is True

    def test_is_subscribed_to_not_subscribed_device(self):
        """Test is_subscribed_to returns False for non-subscribed device."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.add("DEVICE-001")
        assert consumer.is_subscribed_to("DEVICE-002") is False

    def test_subscribed_devices_initially_empty(self):
        """Test that subscribed_devices is empty on init."""
        consumer = TelemetryConsumer()
        assert len(consumer.subscribed_devices) == 0

    def test_subscribe_adds_list_devices(self):
        """Test subscribing adds devices to subscribed_devices."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.update(["DEVICE-001", "DEVICE-002"])
        assert "DEVICE-001" in consumer.subscribed_devices
        assert "DEVICE-002" in consumer.subscribed_devices

    def test_unsubscribe_removes_list_devices(self):
        """Test unsubscribing removes devices from subscribed_devices."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.update(["DEVICE-001", "DEVICE-002"])
        consumer.subscribed_devices.difference_update(["DEVICE-001"])
        assert "DEVICE-001" not in consumer.subscribed_devices
        assert "DEVICE-002" in consumer.subscribed_devices

    def test_subscribe_duplicate_device(self):
        """Test subscribing to same device twice doesn't create duplicates."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.add("DEVICE-001")
        consumer.subscribed_devices.add("DEVICE-001")
        assert len(consumer.subscribed_devices) == 1

    def test_unsubscribe_nonexistent_device(self):
        """Test unsubscribing from non-subscribed device doesn't raise."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.add("DEVICE-001")
        consumer.subscribed_devices.discard("DEVICE-999")
        assert len(consumer.subscribed_devices) == 1


class TestConnectedClientsTracking:
    """Tests for connected_clients tracking."""

    def setup_method(self):
        """Clear connected_clients before each test."""
        connected_clients.clear()

    def test_connected_clients_initially_empty(self):
        """Test connected_clients is empty initially."""
        assert len(connected_clients) == 0

    def test_add_client(self):
        """Test adding client to connected_clients."""
        consumer = TelemetryConsumer()
        connected_clients.add(consumer)
        assert consumer in connected_clients
        assert len(connected_clients) == 1

    def test_add_multiple_clients(self):
        """Test adding multiple clients."""
        consumer1 = TelemetryConsumer()
        consumer2 = TelemetryConsumer()
        connected_clients.add(consumer1)
        connected_clients.add(consumer2)
        assert len(connected_clients) == 2

    def test_remove_client(self):
        """Test removing client from connected_clients."""
        consumer = TelemetryConsumer()
        connected_clients.add(consumer)
        connected_clients.discard(consumer)
        assert consumer not in connected_clients
        assert len(connected_clients) == 0

    def test_remove_nonexistent_client(self):
        """Test removing non-existent client doesn't raise."""
        consumer = TelemetryConsumer()
        connected_clients.discard(consumer)
        assert len(connected_clients) == 0


@pytest.mark.asyncio
class TestBroadcastTelemetry:
    """Tests for broadcast_telemetry function."""

    def setup_method(self):
        """Clear connected_clients before each test."""
        connected_clients.clear()

    async def test_broadcast_no_clients(self):
        """Test broadcast does nothing when no clients connected."""
        data = {"serial_number": "DEVICE-001", "value": 100}
        await broadcast_telemetry(data)

    async def test_broadcast_to_subscribed_client(self):
        """Test broadcast sends to subscribed client."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.add("DEVICE-001")
        consumer.send = AsyncMock()
        connected_clients.add(consumer)

        data = {"serial_number": "DEVICE-001", "value": 100}
        await broadcast_telemetry(data)

        consumer.send.assert_called_once()
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args.kwargs["text_data"])
        assert sent_data["serial_number"] == "DEVICE-001"
        assert sent_data["value"] == 100

    async def test_broadcast_skips_unsubscribed_client(self):
        """Test broadcast skips clients not subscribed to device."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.add("DEVICE-002")
        consumer.send = AsyncMock()
        connected_clients.add(consumer)

        data = {"serial_number": "DEVICE-001", "value": 100}
        await broadcast_telemetry(data)

        consumer.send.assert_not_called()

    async def test_broadcast_to_multiple_subscribed_clients(self):
        """Test broadcast sends to all subscribed clients."""
        consumer1 = TelemetryConsumer()
        consumer1.subscribed_devices.add("DEVICE-001")
        consumer1.send = AsyncMock()

        consumer2 = TelemetryConsumer()
        consumer2.subscribed_devices.add("DEVICE-001")
        consumer2.send = AsyncMock()

        consumer3 = TelemetryConsumer()
        consumer3.subscribed_devices.add("DEVICE-002")
        consumer3.send = AsyncMock()

        connected_clients.add(consumer1)
        connected_clients.add(consumer2)
        connected_clients.add(consumer3)

        data = {"serial_number": "DEVICE-001", "value": 100}
        await broadcast_telemetry(data)

        consumer1.send.assert_called_once()
        consumer2.send.assert_called_once()
        consumer3.send.assert_not_called()

    async def test_broadcast_removes_failed_client(self):
        """Test broadcast removes client that fails to receive."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.add("DEVICE-001")
        consumer.send = AsyncMock(side_effect=Exception("Connection lost"))
        connected_clients.add(consumer)

        data = {"serial_number": "DEVICE-001", "value": 100}
        await broadcast_telemetry(data)

        assert consumer not in connected_clients


class TestMessageParsing:
    """Tests for message parsing and validation."""

    def test_valid_subscribe_message(self):
        """Test parsing valid subscribe message."""
        msg = '{"action": "subscribe", "devices": ["DEVICE-001"]}'
        data = json.loads(msg)
        assert data["action"] == "subscribe"
        assert data["devices"] == ["DEVICE-001"]

    def test_valid_unsubscribe_message(self):
        """Test parsing valid unsubscribe message."""
        msg = '{"action": "unsubscribe", "devices": ["DEVICE-001"]}'
        data = json.loads(msg)
        assert data["action"] == "unsubscribe"

    def test_valid_list_message(self):
        """Test parsing valid list message."""
        msg = '{"action": "list"}'
        data = json.loads(msg)
        assert data["action"] == "list"

    def test_invalid_json(self):
        """Test parsing invalid JSON raises error."""
        msg = "not valid json"
        with pytest.raises(json.JSONDecodeError):
            json.loads(msg)

    def test_subscribe_single_device_as_string(self):
        """Test subscribe with single device as string (not list)."""
        msg = '{"action": "subscribe", "devices": "DEVICE-001"}'
        data = json.loads(msg)
        devices = data.get("devices", [])
        if not isinstance(devices, list):
            devices = [devices]
        assert devices == ["DEVICE-001"]

    def test_filter_invalid_devices(self):
        """Test filtering invalid device values."""
        devices = ["DEVICE-001", None, "", 123, "DEVICE-002"]
        valid_devices = [d for d in devices if d and isinstance(d, str)]
        assert valid_devices == ["DEVICE-001", "DEVICE-002"]


@pytest.mark.asyncio
class TestConsumerReceiveHandlers:
    """Tests for TelemetryConsumer receive handlers."""

    def setup_method(self):
        """Clear connected_clients before each test."""
        connected_clients.clear()

    async def test_handle_subscribe(self):
        """Test _handle_subscribe adds devices."""
        consumer = TelemetryConsumer()
        consumer.send = AsyncMock()
        data = {"devices": ["DEVICE-001", "DEVICE-002"]}

        await consumer._handle_subscribe(data, ("127.0.0.1", 12345))

        assert "DEVICE-001" in consumer.subscribed_devices
        assert "DEVICE-002" in consumer.subscribed_devices
        consumer.send.assert_called_once()

    async def test_handle_subscribe_single_device_string(self):
        """Test _handle_subscribe with single device as string."""
        consumer = TelemetryConsumer()
        consumer.send = AsyncMock()
        data = {"devices": "DEVICE-001"}

        await consumer._handle_subscribe(data, ("127.0.0.1", 12345))

        assert "DEVICE-001" in consumer.subscribed_devices

    async def test_handle_unsubscribe(self):
        """Test _handle_unsubscribe removes devices."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.update(["DEVICE-001", "DEVICE-002"])
        consumer.send = AsyncMock()
        data = {"devices": ["DEVICE-001"]}

        await consumer._handle_unsubscribe(data, ("127.0.0.1", 12345))

        assert "DEVICE-001" not in consumer.subscribed_devices
        assert "DEVICE-002" in consumer.subscribed_devices
        consumer.send.assert_called_once()

    async def test_handle_list(self):
        """Test _handle_list returns current subscriptions."""
        consumer = TelemetryConsumer()
        consumer.subscribed_devices.update(["DEVICE-001", "DEVICE-002"])
        consumer.send = AsyncMock()

        await consumer._handle_list(("127.0.0.1", 12345))

        consumer.send.assert_called_once()
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args.kwargs["text_data"])
        assert sent_data["action"] == "list"
        assert set(sent_data["subscriptions"]) == {"DEVICE-001", "DEVICE-002"}

    async def test_receive_subscribe_action(self):
        """Test receive routes subscribe action correctly."""
        consumer = TelemetryConsumer()
        consumer.scope = {"client": ("127.0.0.1", 12345)}
        consumer.send = AsyncMock()

        await consumer.receive(
            text_data='{"action": "subscribe", "devices": ["DEV-1"]}'
        )

        assert "DEV-1" in consumer.subscribed_devices

    async def test_receive_unsubscribe_action(self):
        """Test receive routes unsubscribe action correctly."""
        consumer = TelemetryConsumer()
        consumer.scope = {"client": ("127.0.0.1", 12345)}
        consumer.subscribed_devices.add("DEV-1")
        consumer.send = AsyncMock()

        await consumer.receive(
            text_data='{"action": "unsubscribe", "devices": ["DEV-1"]}'
        )

        assert "DEV-1" not in consumer.subscribed_devices

    async def test_receive_list_action(self):
        """Test receive routes list action correctly."""
        consumer = TelemetryConsumer()
        consumer.scope = {"client": ("127.0.0.1", 12345)}
        consumer.send = AsyncMock()

        await consumer.receive(text_data='{"action": "list"}')

        consumer.send.assert_called_once()

    async def test_receive_invalid_json(self):
        """Test receive handles invalid JSON."""
        consumer = TelemetryConsumer()
        consumer.scope = {"client": ("127.0.0.1", 12345)}
        consumer.send = AsyncMock()

        await consumer.receive(text_data="not valid json")

        consumer.send.assert_called_once()
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args.kwargs["text_data"])
        assert sent_data["type"] == "error"
        assert sent_data["error"] == "invalid_json"

    async def test_receive_missing_action(self):
        """Test receive handles missing action."""
        consumer = TelemetryConsumer()
        consumer.scope = {"client": ("127.0.0.1", 12345)}
        consumer.send = AsyncMock()

        await consumer.receive(text_data='{"devices": ["DEV-1"]}')

        consumer.send.assert_called_once()
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args.kwargs["text_data"])
        assert sent_data["type"] == "error"
        assert sent_data["error"] == "missing_action"

    async def test_receive_unknown_action(self):
        """Test receive handles unknown action."""
        consumer = TelemetryConsumer()
        consumer.scope = {"client": ("127.0.0.1", 12345)}
        consumer.send = AsyncMock()

        await consumer.receive(text_data='{"action": "unknown_action"}')

        consumer.send.assert_called_once()
        call_args = consumer.send.call_args
        sent_data = json.loads(call_args.kwargs["text_data"])
        assert sent_data["type"] == "error"
        assert sent_data["error"] == "unknown_action"
