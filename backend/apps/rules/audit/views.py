from __future__ import annotations

from typing import Any
from uuid import UUID

from django.core.paginator import Paginator
from django.http import HttpRequest, JsonResponse
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from ..models import RuleAuditLog


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _require_auth(request: HttpRequest, perm: str) -> JsonResponse | None:
    if not request.user.is_authenticated:
        return _error("Authentication credentials were not provided.", 401)
    if not request.user.has_perm(perm):
        return _error("You do not have permission to perform this action.", 403)
    return None


def _parse_positive_int(raw: str, name: str, max_value: int | None = None) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}")
    return value


def _parse_uuid(raw: str, name: str) -> UUID:
    try:
        return UUID(str(raw))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a valid UUID") from exc


def _parse_iso_datetime(raw: str, name: str):
    parsed = parse_datetime(raw)
    if parsed is None:
        raise ValueError(f"{name} must be a valid ISO-8601 datetime")
    return parsed


def _parse_pagination_params(request: HttpRequest) -> tuple[int, int]:
    page = request.GET.get("page", "1")
    page_size = request.GET.get("page_size", "20")
    page_num = _parse_positive_int(page, "page")
    page_size_num = _parse_positive_int(page_size, "page_size", max_value=1000)
    return page_num, page_size_num


def _serialize_rule_audit_log(instance: RuleAuditLog) -> dict[str, Any]:
    return {
        "id": instance.id,
        "created_at": instance.created_at.isoformat(),
        "rule_id": str(instance.rule_id) if instance.rule_id else None,
        "action": instance.action,
        "changed_fields": instance.changed_fields,
        "before": instance.before,
        "after": instance.after,
        "actor_user_id": instance.actor_user_id,
        "actor_username": instance.actor_username,
        "request_id": instance.request_id,
        "source": instance.source,
    }


class RuleAuditFilters:
    def __init__(
        self,
        *,
        rule_id: UUID | None,
        action: str | None,
        from_dt,
        to_dt,
        actor: str | None,
        request_id: str | None,
    ) -> None:
        self.rule_id = rule_id
        self.action = action
        self.from_dt = from_dt
        self.to_dt = to_dt
        self.actor = actor
        self.request_id = request_id

    @classmethod
    def from_request(cls, request: HttpRequest) -> "RuleAuditFilters":
        rule_id_raw = request.GET.get("rule_id")
        parsed_rule_id = _parse_uuid(rule_id_raw, "rule_id") if rule_id_raw else None

        action = request.GET.get("action")
        if action:
            valid_actions = {choice for choice, _ in RuleAuditLog.Action.choices}
            if action not in valid_actions:
                raise ValueError("Invalid action filter value.")

        from_raw = request.GET.get("from")
        to_raw = request.GET.get("to")
        parsed_from = _parse_iso_datetime(from_raw, "from") if from_raw else None
        parsed_to = _parse_iso_datetime(to_raw, "to") if to_raw else None

        if parsed_from and parsed_to and parsed_from > parsed_to:
            raise ValueError("from must be <= to")

        actor = request.GET.get("actor")
        request_id = request.GET.get("request_id")

        return cls(
            rule_id=parsed_rule_id,
            action=action,
            from_dt=parsed_from,
            to_dt=parsed_to,
            actor=actor,
            request_id=request_id,
        )

    def apply(self, queryset):
        if self.rule_id is not None:
            queryset = queryset.filter(rule_id=self.rule_id)

        if self.action:
            queryset = queryset.filter(action=self.action)

        if self.from_dt is not None:
            queryset = queryset.filter(created_at__gte=self.from_dt)

        if self.to_dt is not None:
            queryset = queryset.filter(created_at__lte=self.to_dt)

        if self.actor:
            try:
                actor_user_id = int(self.actor)
                queryset = queryset.filter(actor_user_id=actor_user_id)
            except (TypeError, ValueError):
                queryset = queryset.filter(actor_username__icontains=self.actor)

        if self.request_id:
            queryset = queryset.filter(request_id=self.request_id)

        return queryset


@method_decorator(csrf_exempt, name="dispatch")
class RuleAuditLogListView(View):
    def get(self, request: HttpRequest) -> JsonResponse:
        auth_error = _require_auth(request, "rules.view_ruleauditlog")
        if auth_error is not None:
            return auth_error

        try:
            filters = RuleAuditFilters.from_request(request)
            page_num, page_size_num = _parse_pagination_params(request)
        except ValueError as exc:
            return _error(str(exc), 400)

        queryset = RuleAuditLog.objects.all().order_by("-created_at", "-id")
        queryset = filters.apply(queryset)

        paginator = Paginator(queryset, page_size_num)
        page_obj = paginator.get_page(page_num)

        payload = {
            "data": [_serialize_rule_audit_log(item) for item in page_obj.object_list],
            "pagination": {
                "page": page_obj.number,
                "page_size": page_size_num,
                "total": paginator.count,
                "total_pages": paginator.num_pages,
                "next_page": (
                    page_obj.next_page_number() if page_obj.has_next() else None
                ),
                "prev_page": (
                    page_obj.previous_page_number() if page_obj.has_previous() else None
                ),
            },
        }
        return JsonResponse(payload, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class RuleAuditLogDetailView(View):
    def get(self, request: HttpRequest, audit_id: int) -> JsonResponse:
        auth_error = _require_auth(request, "rules.view_ruleauditlog")
        if auth_error is not None:
            return auth_error

        instance = RuleAuditLog.objects.filter(id=audit_id).first()
        if instance is None:
            return _error("Rule audit log not found.", 404)

        return JsonResponse({"data": _serialize_rule_audit_log(instance)}, status=200)
