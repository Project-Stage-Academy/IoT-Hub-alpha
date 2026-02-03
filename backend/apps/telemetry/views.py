import json
import uuid
import logging
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError, IntegrityError
from django.conf import settings

from .serializer import TelemetrySerializer
from .models import Telemetry
from .tasks import ingest_telemetry_batch_async
from .services import (
    TelemetryValidator,
    TelemetryBatchProcessor,
    TelemetryResponseFormatter,
)

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

    def _handle_db_errors(self, error: Exception, context: str) -> JsonResponse:
        """Handle database errors with appropriate status codes and logging."""
        if isinstance(error, IntegrityError):
            logger.error(f"Database integrity error in {context}", exc_info=True)
            return JsonResponse(
                {"error": "Data integrity error", "details": str(error)}, status=409
            )
        elif isinstance(error, DatabaseError):
            logger.error(f"Database error in {context}", exc_info=True)
            return JsonResponse(
                {"error": "Database error", "details": str(error)}, status=503
            )
        elif isinstance(error, (ValueError, TypeError)):
            logger.error(f"Invalid data type in {context}", exc_info=True)
            return JsonResponse(
                {"error": "Invalid data format", "details": str(error)}, status=400
            )
        else:
            logger.exception(f"Unexpected error in {context}")
            return JsonResponse(
                {"error": "Internal server error", "details": str(error)}, status=500
            )

    def _handle_single_sync(self, data: dict, idempotency_key: str | None):
        validated, error = TelemetryValidator.validate_single(data)
        if error:
            return JsonResponse(error, status=400)

        try:
            telemetry = TelemetryBatchProcessor.process_single(validated)
            response = TelemetryResponseFormatter.format_single_created(
                telemetry, idempotency_key
            )
            return JsonResponse(response, status=201)
        except (IntegrityError, DatabaseError, ValueError, TypeError) as e:
            return self._handle_db_errors(e, "single sync ingestion")

    def _handle_batch_sync(self, data: list, idempotency_key: str | None):
        validated_items, errors = TelemetryValidator.validate_batch(data)

        if errors:
            error_response = TelemetryResponseFormatter.format_validation_error(
                errors, len(data), is_batch=True
            )
            return JsonResponse(error_response, status=400)

        try:
            created = TelemetryBatchProcessor.process_batch(validated_items)
            response = TelemetryResponseFormatter.format_batch_created(
                created, len(data), idempotency_key
            )
            return JsonResponse(response, status=201)
        except (IntegrityError, DatabaseError, ValueError, TypeError) as e:
            return self._handle_db_errors(e, "batch sync ingestion")

    def _handle_async(self, data, is_batch: bool, idempotency_key: str | None):
        request_id = str(uuid.uuid4())
        count = len(data) if is_batch else 1
        items_to_validate = data if is_batch else [data]

        validated_items, errors = TelemetryValidator.validate_batch(items_to_validate)

        if errors:
            error_response = TelemetryResponseFormatter.format_validation_error(
                errors, count, is_batch=False
            )
            return JsonResponse(error_response, status=400)

        try:
            task = ingest_telemetry_batch_async.delay(items_to_validate, request_id)
            task_id = task.id
        except (ConnectionError, TimeoutError) as e:
            logger.error(
                "Failed to connect to task queue",
                extra={"request_id": request_id, "error": str(e)},
            )
            return JsonResponse(
                {"error": "Task queue unavailable", "details": str(e)},
                status=503,
            )
        except (ValueError, TypeError) as e:
            logger.error(
                "Invalid task parameters",
                extra={"request_id": request_id, "error": str(e)},
            )
            return JsonResponse(
                {"error": "Failed to queue task", "details": str(e)},
                status=500,
            )

        response = TelemetryResponseFormatter.format_async_accepted(
            request_id, task_id, count, idempotency_key
        )
        return JsonResponse(response, status=202)
