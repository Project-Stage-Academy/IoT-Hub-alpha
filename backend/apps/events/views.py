from __future__ import annotations

from typing import Any
from uuid import UUID

from django.core.paginator import Paginator
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Event
from .serializer import EventSerializer


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    raise ValueError("must be true/false")


def _parse_positive_int(
    raw: str,
    name: str,
    max_value: int | None = None,
) -> int:
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


def _require_auth(request: HttpRequest, perm: str) -> JsonResponse | None:
    if not request.user.is_authenticated:
        return _error("Authentication credentials were not provided.", 401)
    if not request.user.has_perm(perm):
        return _error("You do not have permission to perform this action.", 403)
    return None


def _get_event_or_error(event_id: int) -> tuple[Event | None, JsonResponse | None]:
    event = Event.objects.select_related("rule__device").filter(id=event_id).first()
    if event is None:
        return None, _error("Event not found.", 404)
    return event, None


@method_decorator(csrf_exempt, name="dispatch")
class EventListView(View):
    def get(self, request: HttpRequest) -> JsonResponse:
        auth_error = _require_auth(request, "events.view_event")
        if auth_error is not None:
            return auth_error

        queryset = Event.objects.select_related("rule__device").all()

        device_id = request.GET.get("device") or request.GET.get("device_id")
        if device_id:
            try:
                parsed_device_id = _parse_uuid(device_id, "device")
            except ValueError as exc:
                return _error(str(exc), 400)
            queryset = queryset.filter(rule__device_id=parsed_device_id)

        rule_id = request.GET.get("rule") or request.GET.get("rule_id")
        if rule_id:
            try:
                parsed_rule_id = _parse_uuid(rule_id, "rule")
            except ValueError as exc:
                return _error(str(exc), 400)
            queryset = queryset.filter(rule_id=parsed_rule_id)

        severity = request.GET.get("severity")
        if severity:
            valid_severities = {choice for choice, _ in Event.EventSeverity.choices}
            if severity not in valid_severities:
                return _error("Invalid severity filter value.", 400)
            queryset = queryset.filter(severity=severity)

        acknowledged = request.GET.get("acknowledged")
        if acknowledged is not None:
            try:
                is_ack = _parse_bool(acknowledged)
            except ValueError:
                return _error("acknowledged must be true/false.", 400)
            if is_ack:
                queryset = queryset.exclude(status=Event.EventStatus.NEW)
            else:
                queryset = queryset.filter(status=Event.EventStatus.NEW)

        page = request.GET.get("page", "1")
        page_size = request.GET.get("page_size", "20")
        try:
            page_num = _parse_positive_int(page, "page")
            page_size_num = _parse_positive_int(
                page_size,
                "page_size",
                max_value=1000,
            )
        except ValueError as exc:
            return _error(str(exc), 400)

        paginator = Paginator(queryset, page_size_num)
        page_obj = paginator.get_page(page_num)
        data = [EventSerializer(instance=item).to_dict() for item in page_obj.object_list]

        payload: dict[str, Any] = {
            "data": data,
            "pagination": {
                "page": page_obj.number,
                "page_size": page_size_num,
                "total": paginator.count,
                "total_pages": paginator.num_pages,
                "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
                "prev_page": page_obj.previous_page_number()
                if page_obj.has_previous()
                else None,
            },
        }
        return JsonResponse(payload, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class EventDetailView(View):
    def get(self, request: HttpRequest, event_id: int) -> JsonResponse:
        auth_error = _require_auth(request, "events.view_event")
        if auth_error is not None:
            return auth_error

        event, not_found_error = _get_event_or_error(event_id)
        if not_found_error is not None:
            return not_found_error
        return JsonResponse({"data": EventSerializer(instance=event).to_dict()}, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class EventAcknowledgeView(View):
    def post(self, request: HttpRequest, event_id: int) -> JsonResponse:
        auth_error = _require_auth(request, "events.change_event")
        if auth_error is not None:
            return auth_error

        event, not_found_error = _get_event_or_error(event_id)
        if not_found_error is not None:
            return not_found_error
        if event.status == Event.EventStatus.NEW:
            event.status = Event.EventStatus.ACKNOWLEDGED
            event.save(update_fields=["status"])

        return JsonResponse({"data": EventSerializer(instance=event).to_dict()}, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class EventResolveView(View):
    def post(self, request: HttpRequest, event_id: int) -> JsonResponse:
        auth_error = _require_auth(request, "events.change_event")
        if auth_error is not None:
            return auth_error

        event, not_found_error = _get_event_or_error(event_id)
        if not_found_error is not None:
            return not_found_error
        if event.status != Event.EventStatus.RESOLVED:
            event.status = Event.EventStatus.RESOLVED
            event.save(update_fields=["status"])

        return JsonResponse({"data": EventSerializer(instance=event).to_dict()}, status=200)
