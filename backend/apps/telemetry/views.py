import json
import uuid
import logging
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.db import transaction
from django.conf import settings

from .serializer import TelemetrySerializer
from .models import Telemetry
from .tasks import ingest_telemetry_batch_async
from .utils import extract_validation_errors

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class TelemetryIngestView(View):
    """POST /api/v1/telemetry/ - ingest single or batched telemetry data"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload"}, status=400)

        idempotency_key = request.headers.get("Idempotency-Key")
        is_batch = isinstance(data, list)

        if is_batch and len(data) > settings.TELEMETRY_MAX_BATCH_SIZE:
            return JsonResponse(
                {
                    "error": (
                        f"Batch size exceeds maximum limit "
                        f"of {settings.TELEMETRY_MAX_BATCH_SIZE} records"
                    )
                },
                status=400,
            )

        if is_batch and len(data) == 0:
            return JsonResponse({"error": "Empty batch provided"}, status=400)

        if settings.TELEMETRY_ASYNC_INGESTION:
            return self._handle_async(data, is_batch, idempotency_key)
        else:
            return self._handle_sync(data, is_batch, idempotency_key)

    def _handle_sync(self, data, is_batch: bool, idempotency_key: str | None):
        if is_batch:
            return self._handle_batch_sync(data, idempotency_key)
        else:
            return self._handle_single_sync(data, idempotency_key)

    def _handle_single_sync(self, data: dict, idempotency_key: str | None):
        try:
            serializer = TelemetrySerializer(data=data)
            validated = serializer.validate_for_bulk()

            with transaction.atomic():
                telemetry = Telemetry.objects.create(**validated)

            response_data = {
                "status": "created",
                "id": telemetry.id,
                "device_id": str(telemetry.device.id),
                "timestamp": telemetry.timestamp.isoformat(),
            }

            if idempotency_key:
                response_data["idempotency_key"] = idempotency_key

            return JsonResponse(response_data, status=201)

        except ValidationError as e:
            return JsonResponse(
                {"error": "Validation failed", "details": extract_validation_errors(e)},
                status=400,
            )
        except Exception as e:
            logger.exception("Unexpected error in single sync ingestion")
            return JsonResponse(
                {"error": "Internal server error", "details": str(e)}, status=500
            )

    def _handle_batch_sync(self, data: list, idempotency_key: str | None):
        validated_items = []
        errors = []

        for idx, item in enumerate(data):
            try:
                serializer = TelemetrySerializer(data=item)
                validated = serializer.validate_for_bulk()
                validated_items.append(validated)
            except ValidationError as e:
                errors.append(
                    {
                        "index": idx,
                        "error": "Validation failed",
                        "details": extract_validation_errors(e),
                    }
                )
            except Exception as e:
                errors.append({"index": idx, "error": str(e)})

        if errors:
            return JsonResponse(
                {
                    "error": "Batch ingestion failed",
                    "details": {
                        "summary": {
                            "total": len(data),
                            "successful": 0,
                            "failed": len(errors),
                        },
                        "errors": errors,
                    },
                },
                status=400,
            )

        try:
            with transaction.atomic():
                telemetry_objects = [
                    Telemetry(**validated) for validated in validated_items
                ]
                created = Telemetry.objects.bulk_create(telemetry_objects)

            created_ids = [obj.id for obj in created]

            response_data = {
                "status": "created",
                "count": len(created_ids),
                "ids": created_ids,
                "summary": {
                    "total": len(data),
                    "successful": len(created_ids),
                    "failed": 0,
                },
            }

            if idempotency_key:
                response_data["idempotency_key"] = idempotency_key

            return JsonResponse(response_data, status=201)

        except Exception as e:
            logger.exception("Unexpected error in batch sync ingestion")
            return JsonResponse(
                {"error": "Internal server error", "details": str(e)}, status=500
            )

    def _handle_async(self, data, is_batch: bool, idempotency_key: str | None):
        request_id = str(uuid.uuid4())
        count = len(data) if is_batch else 1

        validated_items = []
        errors = []

        items_to_validate = data if is_batch else [data]

        for idx, item in enumerate(items_to_validate):
            try:
                serializer = TelemetrySerializer(data=item)
                serializer.validate()
                validated_items.append(item)
            except ValidationError as e:
                errors.append(
                    {
                        "index": idx,
                        "error": "Validation failed",
                        "details": extract_validation_errors(e),
                    }
                )
            except Exception as e:
                errors.append({"index": idx, "error": str(e)})

        if errors:
            return JsonResponse(
                {
                    "error": "Validation failed",
                    "details": {
                        "summary": {
                            "total": count,
                            "successful": 0,
                            "failed": len(errors),
                        },
                        "errors": errors,
                    },
                },
                status=400,
            )

        try:
            task = ingest_telemetry_batch_async.delay(validated_items, request_id)
            task_id = task.id
        except Exception as e:
            logger.exception("Failed to queue telemetry ingestion task")
            return JsonResponse(
                {"error": "Failed to queue ingestion task", "details": str(e)},
                status=500,
            )

        response_data = {
            "status": "accepted",
            "request_id": request_id,
            "count": count,
            "task_id": task_id,
        }

        if idempotency_key:
            response_data["idempotency_key"] = idempotency_key

        return JsonResponse(response_data, status=202)
