from django.urls import path

from apps.telemetry.consumers import TelemetryConsumer

websocket_urlpatterns = [
    path("ws/telemetry/", TelemetryConsumer.as_asgi()),
]
