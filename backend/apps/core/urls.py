from django.urls import path, include

from .views import health, index, metrics, ready

urlpatterns = [
    path("", index, name="index"),
    path("health/", health, name="health"),
    path("api/v1/devices/", include("apps.devices.urls")),
    path("ready/", ready, name="ready"),
    path("metrics/", metrics, name="metrics"),
]
