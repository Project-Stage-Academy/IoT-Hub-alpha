import json
from functools import wraps
from uuid import UUID

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views import View
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Device
from .serializer import DeviceSerializer, DeviceValidator, DeviceRepository
from .exceptions import ApiValidationError, BadRequestError, NotFoundError


def _json_body(request: HttpRequest) -> dict:
    try:
        if not request.body:
            return {}
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise BadRequestError("Invalid JSON body.")


def _parse_uuid(value: str):
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
            return JsonResponse({"detail": e.message}, status=e.status_code)
        except NotFoundError as e:
            return JsonResponse({"detail": e.message}, status=e.status_code)
        except DjangoValidationError as e:
            return JsonResponse({"errors": e.message_dict}, status=400)

    return wrapper


@method_decorator(csrf_exempt, name="dispatch")
class DeviceListView(View):
    default_page_size = 10

    def get(self, request):
        qs = Device.objects.select_related("device_type").order_by("-created_at")

        page_number = request.GET.get("page", 1)
        page_size = int(request.GET.get("page_size", self.default_page_size))
        paginator = Paginator(qs, page_size)

        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            return JsonResponse({"errors": {"page": "Invalid page"}}, status=400)

        data = [
            DeviceSerializer(instance=obj).to_dict() for obj in page_obj.object_list
        ]

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
    def post(self, request: HttpRequest):
        payload = _json_body(request)
        cleaned = DeviceValidator(data=payload, partial=False).validate()
        device = DeviceRepository.save(cleaned)
        device = Device.objects.select_related("device_type").get(id=device.id)
        return JsonResponse(
            {"data": DeviceSerializer(instance=device).to_dict()}, status=201
        )


@method_decorator(csrf_exempt, name="dispatch")
class DeviceDetailView(View):
    def _get_device_or_404(self, device_id):
        try:
            uuid_obj = _parse_uuid(device_id)
            return Device.objects.select_related("device_type").get(id=uuid_obj)
        except Device.DoesNotExist:
            raise NotFoundError("Device not found.")

    @handle_api_errors
    def get(self, request: HttpRequest, device_id):
        obj = self._get_device_or_404(device_id)
        return JsonResponse(
            {"data": DeviceSerializer(instance=obj).to_dict()}, status=200
        )

    def patch(self, request: HttpRequest, device_id):
        return self._update(request, device_id, partial=True)

    def put(self, request: HttpRequest, device_id):
        return self._update(request, device_id, partial=False)

    @handle_api_errors
    def delete(self, request: HttpRequest, device_id):
        obj = self._get_device_or_404(device_id)
        with transaction.atomic():
            obj.delete()
        return HttpResponse(status=204)

    @transaction.atomic
    @handle_api_errors
    def _update(self, request: HttpRequest, device_id, partial: bool):
        obj = self._get_device_or_404(device_id)

        payload = _json_body(request)
        cleaned = DeviceValidator(
            data=payload, partial=partial, instance=obj
        ).validate()
        updated = DeviceRepository.save(cleaned, instance=obj)
        return JsonResponse(
            {"data": DeviceSerializer(instance=updated).to_dict()}, status=200
        )
