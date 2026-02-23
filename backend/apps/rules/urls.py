from django.urls import path

from .views import (
    ExternalRule
)

urlpatterns = [
    path("inbound/<int:inbound_id>", ExternalRule.as_view(), name="external_rule"),
]