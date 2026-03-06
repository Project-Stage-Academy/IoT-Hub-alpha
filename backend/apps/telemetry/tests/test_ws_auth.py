import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from django.contrib.auth import get_user_model

from apps.core.models import WebSocketToken
from apps.telemetry.middleware import (
    WebSocketTokenAuthMiddleware,
    WS_CLOSE_NO_TOKEN,
    WS_CLOSE_INVALID_TOKEN,
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def ws_token(user):
    """Create a WebSocket token for the test user."""
    return WebSocketToken.create_for_user(user)


class TestWebSocketToken:
    """Tests for WebSocketToken model."""

    def test_create_for_user(self, user):
        """Test token creation for user."""
        token = WebSocketToken.create_for_user(user)

        assert token.user == user
        assert len(token.token) == 64  # 32 bytes hex = 64 chars
        assert token.pk is not None

    def test_token_is_unique(self, user):
        """Test that each token is unique."""
        token1 = WebSocketToken.create_for_user(user)
        token2 = WebSocketToken.create_for_user(user)

        assert token1.token != token2.token

    def test_str_representation(self, user):
        """Test string representation of token."""
        token = WebSocketToken.create_for_user(user)
        str_repr = str(token)

        assert "testuser" in str_repr
        assert token.token[:8] in str_repr


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocketTokenAuthMiddleware:
    """Tests for WebSocketTokenAuthMiddleware."""

    async def test_non_websocket_passes_through(self):
        """Test that non-WebSocket requests pass through unchanged."""
        app = AsyncMock()
        middleware = WebSocketTokenAuthMiddleware(app)

        scope = {"type": "http"}
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once_with(scope, receive, send)

    async def test_no_token_closes_connection(self):
        """Test that missing token closes connection with 4001."""
        app = AsyncMock()
        middleware = WebSocketTokenAuthMiddleware(app)

        scope = {
            "type": "websocket",
            "query_string": b"",
            "client": ("127.0.0.1", 8000),
        }
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_not_called()
        # Should accept then close
        assert send.call_count == 2
        send.assert_any_call({"type": "websocket.accept"})
        send.assert_any_call({"type": "websocket.close", "code": WS_CLOSE_NO_TOKEN})

    async def test_invalid_token_closes_connection(self):
        """Test that invalid token closes connection with 4002."""
        app = AsyncMock()
        middleware = WebSocketTokenAuthMiddleware(app)

        scope = {
            "type": "websocket",
            "query_string": b"token=invalid_token_123",
            "client": ("127.0.0.1", 8000),
        }
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_not_called()
        # Should accept then close
        assert send.call_count == 2
        send.assert_any_call({"type": "websocket.accept"})
        send.assert_any_call(
            {"type": "websocket.close", "code": WS_CLOSE_INVALID_TOKEN}
        )

    async def test_valid_token_sets_user_in_scope(self, ws_token):
        """Test that valid token sets user in scope and calls app."""
        app = AsyncMock()
        middleware = WebSocketTokenAuthMiddleware(app)

        scope = {
            "type": "websocket",
            "query_string": f"token={ws_token.token}".encode(),
            "client": ("127.0.0.1", 8000),
        }
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once()
        call_scope = app.call_args[0][0]
        assert call_scope["user"] == ws_token.user

    async def test_token_with_other_query_params(self, ws_token):
        """Test token extraction with other query parameters."""
        app = AsyncMock()
        middleware = WebSocketTokenAuthMiddleware(app)

        scope = {
            "type": "websocket",
            "query_string": f"foo=bar&token={ws_token.token}&baz=qux".encode(),
            "client": ("127.0.0.1", 8000),
        }
        receive = AsyncMock(return_value={"type": "websocket.connect"})
        send = AsyncMock()

        await middleware(scope, receive, send)

        app.assert_called_once()
        call_scope = app.call_args[0][0]
        assert call_scope["user"] == ws_token.user


@pytest.mark.django_db
class TestFakeAuthEndpoint:
    """Tests for the fake auth endpoint."""

    def test_get_creates_token(self, client):
        """Test GET request creates user and token."""
        response = client.get("/api/v1/auth/fake")

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "username" in data
        assert data["username"] == "testuser"
        assert len(data["token"]) == 64

    def test_post_with_custom_username(self, client):
        """Test POST request with custom username."""
        response = client.post(
            "/api/v1/auth/fake",
            data='{"username": "customuser"}',
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "customuser"

    def test_token_is_valid_for_websocket(self, client, db):
        """Test that returned token can be used for WebSocket auth."""
        response = client.get("/api/v1/auth/fake")
        data = response.json()

        # Verify token exists in database
        token = WebSocketToken.objects.get(token=data["token"])
        assert token.user.username == data["username"]
