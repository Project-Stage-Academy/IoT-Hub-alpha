import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

# Track all connected WebSocket clients
connected_clients: set["TelemetryConsumer"] = set()


async def broadcast_telemetry(data: dict) -> None:
    """Broadcast telemetry data to subscribed clients only."""
    if not connected_clients:
        return

    serial_number = data.get("serial_number")
    disconnected = []

    for client in connected_clients:
        # Only send to clients subscribed to this device
        if not client.is_subscribed_to(serial_number):
            continue

        try:
            await client.send(text_data=json.dumps(data))
        except Exception as e:
            logger.warning(
                "websocket.broadcast_failed",
                extra={"error": str(e)},
            )
            disconnected.append(client)

    # Clean up any disconnected clients
    for client in disconnected:
        connected_clients.discard(client)


class TelemetryConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for streaming telemetry data to clients."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No subscriptions by default - client must explicitly subscribe
        self.subscribed_devices: set[str] = set()

    def is_subscribed_to(self, serial_number: str) -> bool:
        """Check if this client is subscribed to the given device."""
        if not self.subscribed_devices:
            return False
        return serial_number in self.subscribed_devices

    async def connect(self):
        """Handle new WebSocket connection."""
        await self.accept()
        connected_clients.add(self)

        # Start Kafka consumer when first client connects
        if len(connected_clients) == 1:
            from apps.telemetry.telemetry_ws_consumer import start_telemetry_consumer

            start_telemetry_consumer()

        client = self.scope.get("client", ("unknown", 0))
        logger.info(
            "websocket.connected",
            extra={
                "client": f"{client[0]}:{client[1]}",
                "total_clients": len(connected_clients),
            },
        )

        # Send welcome message with subscription info
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection",
                    "status": "connected",
                    "subscriptions": list(self.subscribed_devices),
                    "message": "Connected. Subscribe to devices to receive telemetry.",
                }
            )
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        connected_clients.discard(self)

        # Stop Kafka consumer when last client disconnects
        if len(connected_clients) == 0:
            from apps.telemetry.telemetry_ws_consumer import stop_telemetry_consumer

            await stop_telemetry_consumer()

        client = self.scope.get("client", ("unknown", 0))
        logger.info(
            "websocket.disconnected",
            extra={
                "client": f"{client[0]}:{client[1]}",
                "close_code": close_code,
                "total_clients": len(connected_clients),
            },
        )

    async def receive(self, text_data):
        """Handle incoming message from client."""
        client = self.scope.get("client", ("unknown", 0))
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "subscribe":
                await self._handle_subscribe(data, client)
            elif action == "unsubscribe":
                await self._handle_unsubscribe(data, client)
            elif action == "list":
                await self._handle_list(client)
            elif action is None:
                logger.warning(
                    "websocket.missing_action",
                    extra={"client": f"{client[0]}:{client[1]}", "data": data},
                )
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "error": "missing_action",
                            "message": "Message must include an 'action' field",
                            "available_actions": ["subscribe", "unsubscribe", "list"],
                        }
                    )
                )
            else:
                logger.warning(
                    "websocket.unknown_action",
                    extra={
                        "client": f"{client[0]}:{client[1]}",
                        "action": action,
                    },
                )
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "error": "unknown_action",
                            "message": f"Unknown action: {action}",
                            "available_actions": ["subscribe", "unsubscribe", "list"],
                        }
                    )
                )

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "error": "invalid_json",
                        "message": "Message must be valid JSON",
                    }
                )
            )

    async def _handle_subscribe(self, data: dict, client: tuple) -> None:
        """Handle subscribe action."""
        devices = data.get("devices", [])
        if not isinstance(devices, list):
            devices = [devices]

        # Filter valid device serial numbers and add to subscriptions
        valid_devices = [d for d in devices if d and isinstance(d, str)]
        self.subscribed_devices.update(valid_devices)

        logger.info(
            "websocket.subscribed",
            extra={
                "client": f"{client[0]}:{client[1]}",
                "devices": valid_devices,
                "subscriptions": list(self.subscribed_devices),
            },
        )

        await self.send(
            text_data=json.dumps(
                {
                    "type": "subscription",
                    "action": "subscribed",
                    "subscriptions": list(self.subscribed_devices),
                }
            )
        )

    async def _handle_unsubscribe(self, data: dict, client: tuple) -> None:
        """Handle unsubscribe action."""
        devices = data.get("devices", [])
        if not isinstance(devices, list):
            devices = [devices]

        # Filter valid device serial numbers and remove from subscriptions
        valid_devices = [d for d in devices if d and isinstance(d, str)]
        self.subscribed_devices.difference_update(valid_devices)

        logger.info(
            "websocket.unsubscribed",
            extra={
                "client": f"{client[0]}:{client[1]}",
                "devices": valid_devices,
                "subscriptions": list(self.subscribed_devices),
            },
        )

        await self.send(
            text_data=json.dumps(
                {
                    "type": "subscription",
                    "action": "unsubscribed",
                    "subscriptions": list(self.subscribed_devices),
                }
            )
        )

    async def _handle_list(self, client: tuple) -> None:
        """Handle list action - return current subscriptions."""
        logger.info(
            "websocket.list",
            extra={
                "client": f"{client[0]}:{client[1]}",
                "subscriptions": list(self.subscribed_devices),
            },
        )

        await self.send(
            text_data=json.dumps(
                {
                    "type": "subscription",
                    "action": "list",
                    "subscriptions": list(self.subscribed_devices),
                }
            )
        )
