from django.urls import path

from .views import health, index, metrics, ready

urlpatterns = [
    path("", index, name="index"),
    path("health/", health, name="health"),
    path("ready/", ready, name="ready"),
    path("metrics/", metrics, name="metrics"),
]
