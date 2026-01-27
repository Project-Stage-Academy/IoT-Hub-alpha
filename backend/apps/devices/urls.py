from django.urls import path
from .views import DeviceListView, DeviceDetailView

urlpatterns = [
    # LIST + CREATE
    path("", DeviceListView.as_view(), name="device-list"),

    # RETRIEVE + UPDATE + DELETE
    path("<uuid:device_id>/", DeviceDetailView.as_view(), name="device-detail"),
]
