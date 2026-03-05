from django.urls import path, include

from .views import fake_auth, health, index, metrics, ready

urlpatterns = [
    path("", index, name="index"),
    path("health/", health, name="health"),
    path("api/v1/devices/", include("apps.devices.urls")),
    path("api/v1/events/", include("apps.events.urls")),
    path("api/v1/rules/", include("apps.rules.urls")),
    path("api/v1/auth/fake", fake_auth, name="fake_auth"),
    path("ready/", ready, name="ready"),
    path("metrics/", metrics, name="metrics"),
]
