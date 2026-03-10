from django import forms
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
import logging

from .admin_widget import HelpWidget
from .audit import bind_audit_actor, get_request_id_from_request, reset_audit_actor
from .models import Rule, RuleAuditLog, validate_action_config, validate_condition

logger = logging.getLogger(__name__)


def _safe_bulk_create_audit_logs(logs) -> None:
    try:
        RuleAuditLog.objects.bulk_create(logs)
    except Exception:
        logger.exception(
            "rule_audit_bulk_write_failed",
            extra={"count": len(logs)},
        )


def _bulk_toggle_with_audit(queryset, request, target_enabled: bool) -> int:
    candidate_rows = list(
        queryset.filter(is_enabled=not target_enabled).values("id", "is_enabled")
    )

    if not candidate_rows:
        return 0

    candidate_ids = [row["id"] for row in candidate_rows]
    updated = Rule.objects.filter(id__in=candidate_ids).update(
        is_enabled=target_enabled
    )

    user = getattr(request, "user", None)
    actor_user_id = user.id if user and user.is_authenticated else None
    actor_username = user.get_username() if user and user.is_authenticated else None
    request_id = get_request_id_from_request(request)
    action = (
        RuleAuditLog.Action.ENABLE if target_enabled else RuleAuditLog.Action.DISABLE
    )

    logs = [
        RuleAuditLog(
            rule_id=row["id"],
            action=action,
            changed_fields=["is_enabled"],
            before={"is_enabled": row["is_enabled"]},
            after={"is_enabled": target_enabled},
            actor_user_id=actor_user_id,
            actor_username=actor_username,
            request_id=request_id,
            source=RuleAuditLog.Source.ADMIN_ACTION,
        )
        for row in candidate_rows
    ]

    transaction.on_commit(
        lambda: _safe_bulk_create_audit_logs(logs),
        robust=True,
    )
    return updated


@admin.action(description="Enable selected rules")
def enable_rules(modeladmin, request, queryset):
    """
    Django admin action to enable selected rules.

    Bulk-updates is_enabled=True for selected Rule instances and displays
    success message with count. Called from Rule admin change list when user
    selects rules and chooses "Enable selected rules" action.

    Args:
        modeladmin: RuleAdmin instance
        request: HTTP request object
        queryset: QuerySet of Rule instances to enable
    """
    updated = _bulk_toggle_with_audit(queryset, request, target_enabled=True)
    modeladmin.message_user(
        request,
        f"{updated} rule(s) enabled.",
        messages.SUCCESS,
    )


@admin.action(description="Disable selected rules")
def disable_rules(modeladmin, request, queryset):
    """
    Django admin action to disable selected rules.

    Bulk-updates is_enabled=False for selected Rule instances and displays
    success message with count. Called from Rule admin change list when user
    selects rules and chooses "Disable selected rules" action.

    Args:
        modeladmin: RuleAdmin instance
        request: HTTP request object
        queryset: QuerySet of Rule instances to disable
    """
    updated = _bulk_toggle_with_audit(queryset, request, target_enabled=False)
    modeladmin.message_user(
        request,
        f"{updated} rule(s) disabled.",
        messages.SUCCESS,
    )


class RuleAdminForm(forms.ModelForm):
    class Meta:
        model = Rule
        fields = "__all__"

    def clean_condition(self):
        value = self.cleaned_data.get("condition")
        validate_condition(value)
        return value

    def clean_action_config(self):
        value = self.cleaned_data.get("action_config")
        validate_action_config(value)
        return value


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):

    class Media:
        js = ("admin/condition_ui.js",)
        css = {"all": ("admin/condition_ui.css",)}

    form = RuleAdminForm

    list_display = [
        "name",
        "device",
        "condition",
        "is_enabled",
        "last_triggered_at",
        "created_at",
    ]
    list_filter = ["is_enabled", "device", "created_at"]
    search_fields = ["name", "description", "device__name", "device__serial_number"]
    readonly_fields = ["id", "created_at", "updated_at", "last_triggered_at"]
    date_hierarchy = "created_at"
    actions = [enable_rules, disable_rules]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)

        if db_field.name == "condition":
            formfield.widget = HelpWidget(
                attrs={"rows": 8, "style": "width:100%;"}, target="condition"
            )

        if db_field.name == "action_config":
            formfield.widget = HelpWidget(
                target="action",
                attrs={"rows": 8, "style": "width:100%;"},
            )

        return formfield

    def save_model(self, request, obj, form, change):
        if change:
            if not request.user.has_perm("rules.change_rule"):
                raise PermissionDenied("You can't update rules.")
        else:
            if not request.user.has_perm("rules.add_rule"):
                raise PermissionDenied("You can't create rules.")

        if not change and hasattr(obj, "created_by_id") and not obj.created_by_id:
            obj.created_by = request.user

        token = bind_audit_actor(request.user)
        try:
            super().save_model(request, obj, form, change)
        finally:
            reset_audit_actor(token)

    def delete_model(self, request, obj):
        token = bind_audit_actor(request.user)
        try:
            super().delete_model(request, obj)
        finally:
            reset_audit_actor(token)

    def delete_queryset(self, request, queryset):
        token = bind_audit_actor(request.user)
        try:
            super().delete_queryset(request, queryset)
        finally:
            reset_audit_actor(token)
