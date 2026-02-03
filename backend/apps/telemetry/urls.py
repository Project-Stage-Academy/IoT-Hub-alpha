from django.urls import path
from . import views

urlpatterns = [
    path("", views.TelemetryIngestView.as_view(), name="telemetry_ingest"),
]
