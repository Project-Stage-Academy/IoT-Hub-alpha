from __future__ import annotations

import json
from functools import wraps
from uuid import UUID

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.rules.services.view_helpers import get_json_body
from apps.rules.services.inbound_transform import TransformEngine, TransformationError

from .exceptions import ApiValidationError, BadRequestError, NotFoundError
from .models import Rule
from .serializer import (
    RuleRepository,
    RuleSerializer,
    RuleValidator,
)


def _json_body(request: HttpRequest) -> dict:
    try:
        if not request.body:
            return {}
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise BadRequestError("Invalid JSON body.")


def _parse_uuid(value: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise BadRequestError("Invalid UUID format.")


def handle_api_errors(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except ApiValidationError as e:
            return JsonResponse({"errors": e.errors}, status=e.status_code)
        except BadRequestError as e:
            return JsonResponse({"error": e.message}, status=e.status_code)
        except NotFoundError as e:
            return JsonResponse({"error": e.message}, status=e.status_code)

    return wrapper


@method_decorator(csrf_exempt, name="dispatch")
class RuleListView(View):
    default_page_size = 10

    def get(self, request: HttpRequest) -> JsonResponse:
        qs = Rule.objects.select_related("device").order_by("-created_at")

        device_id = request.GET.get("device_id")
        if device_id:
            try:
                device_uuid = _parse_uuid(device_id)
            except BadRequestError:
                return JsonResponse({"error": "Invalid device_id format."}, status=400)
            qs = qs.filter(device_id=device_uuid)

        is_enabled = request.GET.get("is_enabled")
        if is_enabled is not None:
            qs = qs.filter(is_enabled=is_enabled.lower() in ("true", "1", "yes"))

        page_number = request.GET.get("page", 1)
        page_size = int(request.GET.get("page_size", self.default_page_size))
        paginator = Paginator(qs, page_size)

        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            return JsonResponse({"errors": {"page": "Invalid page"}}, status=400)

        data = [RuleSerializer(instance=obj).to_dict() for obj in page_obj.object_list]

        return JsonResponse(
            {
                "data": data,
                "pagination": {
                    "page": page_obj.number,
                    "page_size": page_size,
                    "total": paginator.count,
                    "total_pages": paginator.num_pages,
                    "next_page": (
                        page_obj.next_page_number() if page_obj.has_next() else None
                    ),
                    "prev_page": (
                        page_obj.previous_page_number()
                        if page_obj.has_previous()
                        else None
                    ),
                },
            },
            status=200,
        )

    @handle_api_errors
    def post(self, request: HttpRequest) -> JsonResponse:
        payload = _json_body(request)
        cleaned = RuleValidator(data=payload, partial=False).validate()
        rule = RuleRepository.save(cleaned)
        rule = Rule.objects.select_related("device").get(pk=rule.pk)
        return JsonResponse(
            {"data": RuleSerializer(instance=rule).to_dict()}, status=201
        )


@method_decorator(csrf_exempt, name="dispatch")
class RuleDetailView(View):
    def _get_rule_or_404(self, rule_id):
        try:
            uuid_obj = _parse_uuid(rule_id)
            return Rule.objects.select_related("device").get(pk=uuid_obj)
        except Rule.DoesNotExist:
            raise NotFoundError("Rule not found.")

    @handle_api_errors
    def get(self, request: HttpRequest, rule_id) -> JsonResponse:
        obj = self._get_rule_or_404(rule_id)
        return JsonResponse(
            {"data": RuleSerializer(instance=obj).to_dict()}, status=200
        )

    @handle_api_errors
    def patch(self, request: HttpRequest, rule_id) -> JsonResponse:
        obj = self._get_rule_or_404(rule_id)
        payload = _json_body(request)
        cleaned = RuleValidator(data=payload, partial=True, instance=obj).validate()
        updated = RuleRepository.save(cleaned, instance=obj)
        return JsonResponse(
            {"data": RuleSerializer(instance=updated).to_dict()}, status=200
        )

    @handle_api_errors
    def delete(self, request: HttpRequest, rule_id) -> HttpResponse:
        obj = self._get_rule_or_404(rule_id)
        with transaction.atomic():
            obj.delete()
        return HttpResponse(status=204)


@method_decorator(csrf_exempt, name="dispatch")
class ExternalRule(View):
    """
    Recieve external event and generates an internally complient instance
    of event.topic
    """

    def post(self, request: HttpRequest, inbound_id) -> JsonResponse:

        engine = TransformEngine()

        parsed_body = get_json_body(request.body)
        if not parsed_body:
            return JsonResponse({"error": "Empty body"}, status=400)

        try:
            transformed = engine.transform(inbound_id, parsed_body)
        except TransformationError as e:
            return JsonResponse({"error": f"Failed: {e}"}, status=400)

        return JsonResponse(transformed.model_dump(), status=202)
