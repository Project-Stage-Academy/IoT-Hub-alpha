"""Core application views for health checks and metrics."""

import json
import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, OperationalError, connection
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from prometheus_client import generate_latest

from apps.core.models import WebSocketToken

logger = logging.getLogger(__name__)
User = get_user_model()


def index(request):  # noqa: ARG001
    """Health index endpoint - confirms system is online."""
    return HttpResponse("IoT Hub Alpha: System Online")


def health(request):  # noqa: ARG001
    """Liveness probe - checks if service is running."""
    return HttpResponse("ok")


def ready(request):  # noqa: ARG001
    """Readiness probe - checks if service is ready to handle traffic (DB connected)."""
    try:
        connection.ensure_connection()
        return HttpResponse("ready", status=200)

    except (OperationalError, DatabaseError) as e:
        # Database connection failed or not available
        logger.warning(
            "Readiness check failed - DB error: %s: %s",
            type(e).__name__,
            e,
        )
        return HttpResponse("not ready", status=503)

    except ImproperlyConfigured as e:
        # Database not configured properly
        logger.error("Readiness check failed - DB misconfigured: %s", e)
        return HttpResponse("misconfigured", status=500)


def metrics(request):  # noqa: ARG001
    """Expose Prometheus metrics endpoint."""
    return HttpResponse(
        generate_latest(),
        content_type="text/plain; charset=utf-8",
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def fake_auth(request):
    """
    Fake authentication endpoint for testing WebSocket connections.

    GET: Creates or retrieves a test user and returns a WebSocket token.
    POST: Accepts optional username in JSON body.

    Response: {"token": "xxx...", "username": "testuser"}
    """
    username = "testuser"

    if request.method == "POST":
        try:
            body = json.loads(request.body)
            username = body.get("username", username)
        except json.JSONDecodeError:
            pass

    # Get or create test user
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={"email": f"{username}@test.local"},
    )

    # Create new token for user
    ws_token = WebSocketToken.create_for_user(user)

    logger.info(
        "fake_auth.token_created",
        extra={"username": username, "token": ws_token.token[:8]},
    )

    return JsonResponse(
        {
            "token": ws_token.token,
            "username": user.username,
        }
    )
