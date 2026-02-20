import json
import uuid
import logging
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.conf import settings

from .tasks import ingest_telemetry_batch_async
from .kafka import TelemetryKafkaProducer, KafkaProducerError
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

        serial_number = request.headers.get("X-Device-Serial-Number")
        if not serial_number:
            return JsonResponse(
                {"error": "X-Device-Serial-Number header is required"}, status=400
            )

        idempotency_key = request.headers.get("Idempotency-Key")
        is_batch = isinstance(data, list)

        # Inject serial_number into data for serializer
        if is_batch:
            for item in data:
                item["serial_number"] = serial_number
        else:
            data["serial_number"] = serial_number

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

        if settings.TELEMETRY_PIPELINE_MODE == "kafka":
            return self._handle_kafka(data, is_batch, idempotency_key, serial_number)

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
            logger.exception(
                "Database integrity error",
                extra={"context": context, "error_type": error.__class__.__name__},
            )
            return JsonResponse({"error": "Processing failed"}, status=409)
        elif isinstance(error, DatabaseError):
            logger.exception(
                "Database error",
                extra={"context": context, "error_type": error.__class__.__name__},
            )
            return JsonResponse({"error": "Processing failed"}, status=503)
        elif isinstance(error, (ValueError, TypeError)):
            logger.exception(
                "Invalid data type",
                extra={"context": context, "error_type": error.__class__.__name__},
            )
            return JsonResponse({"error": "Invalid data"}, status=400)
        else:
            logger.exception(
                "Unexpected error",
                extra={"context": context, "error_type": error.__class__.__name__},
            )
            return JsonResponse({"error": "Processing failed"}, status=500)

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

        serialized_items = []
        for item in validated_items:
            serialized = {
                "device_id": str(item["device"].id),
                "payload": item["payload"],
            }
            if "timestamp" in item:
                serialized["timestamp"] = item["timestamp"].isoformat()
            serialized_items.append(serialized)

        try:
            task = ingest_telemetry_batch_async.delay(serialized_items, request_id)
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

    def _handle_kafka(
        self, data, is_batch: bool, idempotency_key: str | None, serial_number: str
    ):
        request_id = str(uuid.uuid4())
        count = len(data) if is_batch else 1
        items_to_publish = data if is_batch else [data]

        received_at = timezone.now().isoformat()
        kafka_messages = []
        for index, item in enumerate(items_to_publish):
            msg = {
                "request_id": request_id,
                "ingest_protocol": "http",
                "serial_number": item["serial_number"],
                "payload": item,
                "received_at": received_at,
                "ingest_index": index,
            }
            kafka_messages.append(msg)

        producer = TelemetryKafkaProducer()
        target_topic = producer.resolve_topic(
            application="telemetry",
            serial_number=serial_number,
        )

        try:
            headers = [
                ("ingest_protocol", b"http"),
            ]
            producer.publish_batch(
                kafka_messages,
                topic=target_topic,
                headers=headers,
            )
        except KafkaProducerError as exc:
            logger.exception(
                "Kafka publish failed",
                extra={
                    "request_id": request_id,
                    "topic": target_topic,
                    "count": count,
                },
            )
            return JsonResponse(
                {"error": "Kafka publish failed", "details": str(exc)}, status=503
            )

        response = TelemetryResponseFormatter.format_async_accepted(
            request_id=request_id,
            task_id="kafka",
            count=count,
            idempotency_key=idempotency_key,
        )
        response["topic"] = target_topic
        response["pipeline_mode"] = settings.TELEMETRY_PIPELINE_MODE
        return JsonResponse(response, status=202)
