from django.urls import path

from .views import health, index, metrics

urlpatterns = [
    path("", index, name="index"),
    path("health/", health, name="health"),
    path("metrics/", metrics, name="metrics"),
]
