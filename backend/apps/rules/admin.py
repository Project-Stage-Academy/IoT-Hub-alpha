from django import forms
from django.contrib import admin
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.urls import path
from django.shortcuts import redirect
from .models import Rule
from .tasks import process_telemetry


@admin.action(description="Enable selected rules")
def enable_rules(modeladmin, request, queryset):
    updated = queryset.update(is_enabled=True)
    modeladmin.message_user(
        request,
        f"{updated} rule(s) enabled.",
        messages.SUCCESS,
    )


@admin.action(description="Disable selected rules")
def disable_rules(modeladmin, request, queryset):
    updated = queryset.update(is_enabled=False)
    modeladmin.message_user(
        request,
        f"{updated} rule(s) disabled.",
        messages.SUCCESS,
    )


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "device",
        "comparison_operator",
        "threshold",
        "is_enabled",
        "last_triggered_at",
        "created_at",
    ]
    list_filter = ["is_enabled", "comparison_operator", "device", "created_at"]
    search_fields = ["name", "description", "device__name", "device__serial_number"]
    readonly_fields = ["id", "created_at", "updated_at", "last_triggered_at"]
    date_hierarchy = "created_at"
    actions = [enable_rules, disable_rules]
    change_list_template = "admin/rules/rule/change_list.html"  # <- important

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "run-processor/",
                self.admin_site.admin_view(self.run_processor_view),
                name="rules_rule_run_processor",
            ),
        ]
        return custom + urls

    def run_processor_view(self, request: HttpRequest) -> HttpResponse:
        # Optional: permission gate (usually staff already, but be explicit)
        if not self.has_change_permission(request):
            self.message_user(request, "Permission denied.", level=messages.ERROR)
            return redirect("..")

        # Enqueue Celery task (don’t call the function directly!)
        result = process_telemetry.delay()

        self.message_user(
            request,
            f"Enqueued process_telemetry. Task id: {result.id}",
            level=messages.SUCCESS,
        )
        return redirect("..")
