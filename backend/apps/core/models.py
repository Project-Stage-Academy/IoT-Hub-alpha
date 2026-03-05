import secrets

from django.conf import settings
from django.db import models


class WebSocketToken(models.Model):
    """Token for authenticating WebSocket connections."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="websocket_tokens",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"WebSocketToken for {self.user} ({self.token[:8]}...)"

    @classmethod
    def create_for_user(cls, user) -> "WebSocketToken":
        """Create a new token for the given user."""
        return cls.objects.create(user=user, token=secrets.token_hex(32))
