from django.urls import path

from .views import health, index

urlpatterns = [
    path("", index, name="index"),
    path("health/", health, name="health"),
]
