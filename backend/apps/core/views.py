"""Core application views for health checks and metrics."""

import logging

from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, OperationalError, connection
from django.http import HttpResponse
from prometheus_client import generate_latest

logger = logging.getLogger(__name__)


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
