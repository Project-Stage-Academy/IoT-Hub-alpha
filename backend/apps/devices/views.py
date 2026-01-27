import json

from django.http import JsonResponse, HttpRequest
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Device
from .serializer import DeviceSerializer, ApiValidationError


def _json_body(request: HttpRequest) -> dict:
    try:
        if not request.body:
            return {}
        return json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise ApiValidationError({"detail": "Invalid JSON body."}, status_code=400)


@method_decorator(csrf_exempt, name="dispatch")
class DeviceListView(View):
    def get(self, request: HttpRequest):
        qs = Device.objects.all().order_by("-created_at")
        data = [DeviceSerializer(instance=obj).to_dict() for obj in qs]
        return JsonResponse({"devices": data, "count": len(data)}, status=200)

    def post(self, request: HttpRequest):
        try:
            payload = _json_body(request)
            device = DeviceSerializer(data=payload, partial=False).save()
            return JsonResponse({"data": DeviceSerializer(instance=device).to_dict()}, status=201)
        except ApiValidationError as e:
            return JsonResponse({"errors": e.errors}, status=e.status_code)
        except DjangoValidationError as e:
            # якщо full_clean() кинув помилки моделі
            return JsonResponse({"errors": e.message_dict}, status=400)


@method_decorator(csrf_exempt, name="dispatch")
class DeviceDetailView(View):
    def get(self, request: HttpRequest, device_id):
        try:
            obj = Device.objects.get(id=device_id)
            return JsonResponse({"data": DeviceSerializer(instance=obj).to_dict()}, status=200)
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
            return JsonResponse({}, status=204)
        except Device.DoesNotExist:
            return JsonResponse({"detail": "Not found."}, status=404)

    def _update(self, request: HttpRequest, device_id, partial: bool):
        try:
            obj = Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            return JsonResponse({"detail": "Not found."}, status=404)

        try:
            payload = _json_body(request)
            updated = DeviceSerializer(instance=obj, data=payload, partial=partial).save()
            return JsonResponse({"data": DeviceSerializer(instance=updated).to_dict()}, status=200)
        except ApiValidationError as e:
            return JsonResponse({"errors": e.errors}, status=e.status_code)
        except DjangoValidationError as e:
            return JsonResponse({"errors": e.message_dict}, status=400)
