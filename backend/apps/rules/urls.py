from django.urls import path

from .views import ExternalRule, RuleListView, RuleDetailView

urlpatterns = [
    path("", RuleListView.as_view(), name="rule-list"),
    path("<uuid:rule_id>/", RuleDetailView.as_view(), name="rule-detail"),
    path("inbound/<int:inbound_id>", ExternalRule.as_view(), name="external_rule"),
]
