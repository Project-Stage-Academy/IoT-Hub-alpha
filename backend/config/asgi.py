import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django ASGI application early to ensure settings are loaded
django_asgi_app = get_asgi_application()

# Import WebSocket routing and middleware after Django is initialized
from apps.telemetry.middleware import WebSocketTokenAuthMiddleware
from apps.telemetry.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": WebSocketTokenAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
