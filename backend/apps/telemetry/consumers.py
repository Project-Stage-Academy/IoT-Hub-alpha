import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class TelemetryConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for streaming telemetry data to clients."""

    async def connect(self):
        """Handle new WebSocket connection."""
        await self.accept()
        client = self.scope.get("client", ("unknown", 0))
        logger.info(
            "websocket.connected",
            extra={"client": f"{client[0]}:{client[1]}"},
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        client = self.scope.get("client", ("unknown", 0))
        logger.info(
            "websocket.disconnected",
            extra={"client": f"{client[0]}:{client[1]}", "close_code": close_code},
        )

    async def receive(self, text_data):
        """Handle incoming message from client."""
        client = self.scope.get("client", ("unknown", 0))
        try:
            data = json.loads(text_data)
            logger.info(
                "websocket.message_received",
                extra={"client": f"{client[0]}:{client[1]}", "data": data},
            )
            # Echo back for testing
            await self.send(text_data=json.dumps({"status": "received", "data": data}))
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
