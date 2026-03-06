import logging
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)

# WebSocket close codes for authentication errors
WS_CLOSE_NO_TOKEN = 4001
WS_CLOSE_INVALID_TOKEN = 4002


class WebSocketTokenAuthMiddleware:
    """
    Middleware for authenticating WebSocket connections via query string token.

    Usage: ws://host/ws/telemetry/?token=xxx

    Close codes:
        4001 - No token provided
        4002 - Invalid token
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "websocket":
            return await self.app(scope, receive, send)

        # Extract token from query string
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if not token:
            logger.warning(
                "websocket.auth_failed",
                extra={"reason": "no_token", "client": scope.get("client")},
            )
            await self._close_connection(receive, send, WS_CLOSE_NO_TOKEN)
            return

        # Validate token and get user
        user = await self._get_user_from_token(token)

        if user is None:
            logger.warning(
                "websocket.auth_failed",
                extra={"reason": "invalid_token", "client": scope.get("client")},
            )
            await self._close_connection(receive, send, WS_CLOSE_INVALID_TOKEN)
            return

        # Set user in scope for consumer
        scope["user"] = user
        logger.info(
            "websocket.auth_success",
            extra={"user": user.username, "client": scope.get("client")},
        )

        return await self.app(scope, receive, send)

    @database_sync_to_async
    def _get_user_from_token(self, token: str):
        """Look up user by WebSocket token."""
        from apps.core.models import WebSocketToken

        try:
            ws_token = WebSocketToken.objects.select_related("user").get(token=token)
            return ws_token.user
        except WebSocketToken.DoesNotExist:
            return None

    async def _close_connection(self, receive, send, code: int):
        """Accept WebSocket connection, then close with given code."""
        # Wait for the client to initiate the connection
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                break

        # Accept then immediately close with error code
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": code})
