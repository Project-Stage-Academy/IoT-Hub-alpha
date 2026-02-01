import json
from functools import wraps

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Device
from .serializer import DeviceSerializer, ApiValidationError


def _json_body(request: HttpRequest) -> dict:
    try:
        if not request.body:
            return {}
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ApiValidationError({"detail": "Invalid JSON body."}, status_code=400)


def handle_api_errors(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        try:
            return view_func(*args, **kwargs)
        except ApiValidationError as e:
            return JsonResponse({"errors": e.errors}, status=e.status_code)
        except DjangoValidationError as e:
            return JsonResponse({"errors": e.message_dict}, status=400)
        except ValueError as e:
            return JsonResponse({"detail": str(e)}, status=400)

    return wrapper


@method_decorator(csrf_exempt, name="dispatch")
class DeviceListView(View):
    def get(self, request):
        qs = Device.objects.all().order_by("-created_at")

        page_number = request.GET.get("page", 1)
        page_size = 10
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
        device = DeviceSerializer(data=payload, partial=False).save()
        return JsonResponse(
            {"data": DeviceSerializer(instance=device).to_dict()}, status=201
        )


@method_decorator(csrf_exempt, name="dispatch")
class DeviceDetailView(View):
    def get(self, request: HttpRequest, device_id):
        try:
            obj = Device.objects.get(id=device_id)
            return JsonResponse(
                {"data": DeviceSerializer(instance=obj).to_dict()}, status=200
            )
        except Device.DoesNotExist:
            return JsonResponse({"detail": "Not found."}, status=404)

    def patch(self, request: HttpRequest, device_id):
        return self._update(request, device_id, partial=True)

    def put(self, request: HttpRequest, device_id):
        return self._update(request, device_id, partial=False)

    def delete(self, request: HttpRequest, device_id):
        try:
            obj = Device.objects.get(id=device_id)
            obj.delete()
            return HttpResponse(status=204)
        except Device.DoesNotExist:
            return JsonResponse({"detail": "Not found."}, status=404)

    @handle_api_errors
    def _update(self, request: HttpRequest, device_id, partial: bool):
        try:
            obj = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            return JsonResponse({"detail": "Not found."}, status=404)

        payload = _json_body(request)
        updated = DeviceSerializer(instance=obj, data=payload, partial=partial).save()
        return JsonResponse(
            {"data": DeviceSerializer(instance=updated).to_dict()}, status=200
        )
