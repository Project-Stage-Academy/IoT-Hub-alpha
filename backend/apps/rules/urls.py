from django.urls import path

from .audit.views import RuleAuditLogDetailView, RuleAuditLogListView
from .views import ExternalRule

urlpatterns = [
    path("inbound/<int:inbound_id>", ExternalRule.as_view(), name="external_rule"),
    path("audit/", RuleAuditLogListView.as_view(), name="rule_audit_list"),
    path(
        "audit/<int:audit_id>/",
        RuleAuditLogDetailView.as_view(),
        name="rule_audit_detail",
    ),
]
