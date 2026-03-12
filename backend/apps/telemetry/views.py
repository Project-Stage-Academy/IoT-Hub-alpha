import json
import uuid
import logging
import hashlib

from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.conf import settings

from .kafka import (
    KafkaDeliveryError,
    KafkaProducerError,
    KafkaPublishError,
    TelemetryKafkaProducer,
)
from .tasks import ingest_telemetry_batch_async
from .producers import build_raw_event, get_producer
from .services import (
    TelemetryValidator,
    TelemetryBatchProcessor,
    TelemetryResponseFormatter,
)
from apps.rules.services.metrics import record_telemetry_ingested

logger = logging.getLogger(__name__)


def _build_http_idempotency_key(*, serial_number: str, payload: object) -> str:
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    hasher = hashlib.sha256()
    hasher.update(serial_number.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(canonical_payload.encode("utf-8"))
    return f"http:{hasher.hexdigest()}"


def _build_http_batch_item_idempotency_key(
    *,
    batch_idempotency_key: str | None,
    ingest_index: int,
) -> str | None:
    if batch_idempotency_key is None:
        return None
    return f"{batch_idempotency_key}:{ingest_index}"


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

        idempotency_header = request.headers.get("Idempotency-Key")
        idempotency_key = (
            idempotency_header.strip()
            if isinstance(idempotency_header, str) and idempotency_header.strip()
            else None
        )
        is_batch = isinstance(data, list)

        # Inject serial_number into data for serializer
        if is_batch:
            for item in data:
                item["serial_number"] = serial_number
                item.pop("ssn", None)
        else:
            data["serial_number"] = serial_number
            data.pop("ssn", None)
        if idempotency_key is None:
            idempotency_key = _build_http_idempotency_key(
                serial_number=serial_number,
                payload=data,
            )

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

    @staticmethod
    def _is_idempotency_conflict(error: IntegrityError) -> bool:
        lowered = str(error).lower()
        idempotency_markers = ("idempotency", "idempotency_key", "idempotency-key")
        duplicate_markers = (
            "duplicate key",
            "already exists",
            "unique constraint",
            "unique failed",
        )
        return any(marker in lowered for marker in idempotency_markers) and any(
            marker in lowered for marker in duplicate_markers
        )

    def _handle_db_errors(self, error: Exception, context: str) -> JsonResponse:
        """Handle database errors with appropriate status codes and logging."""
        if isinstance(error, IntegrityError):
            is_idempotency_conflict = self._is_idempotency_conflict(error)
            logger.exception(
                "Database integrity error",
                extra={
                    "context": context,
                    "error_type": error.__class__.__name__,
                    "is_idempotency_conflict": is_idempotency_conflict,
                },
            )
            return JsonResponse(
                {"error": "Processing failed"},
                status=409 if is_idempotency_conflict else 500,
            )
        if isinstance(error, DatabaseError):
            logger.exception(
                "Database error",
                extra={"context": context, "error_type": error.__class__.__name__},
            )
            return JsonResponse({"error": "Processing failed"}, status=500)
        if isinstance(error, (ValueError, TypeError)):
            logger.exception(
                "Invalid data type",
                extra={"context": context, "error_type": error.__class__.__name__},
            )
            return JsonResponse({"error": "Invalid data"}, status=400)
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
        self,
        data,
        is_batch: bool,
        idempotency_key: str | None,
        serial_number: str,
    ):
        request_id = str(uuid.uuid4())
        count = len(data) if is_batch else 1
        items_to_publish = data if is_batch else [data]

        validated_items, errors = TelemetryValidator.validate_batch(items_to_publish)

        if errors:
            error_response = TelemetryResponseFormatter.format_validation_error(
                errors, count, is_batch=is_batch
            )
            return JsonResponse(error_response, status=400)

        received_at = timezone.now().isoformat()

        producer = get_producer()
        target_topic: str | None = None

        try:
            if is_batch:
                events = [
                    build_raw_event(
                        item,
                        source="http",
                        serial_number=serial_number,
                        request_id=request_id,
                        idempotency_key=_build_http_batch_item_idempotency_key(
                            batch_idempotency_key=idempotency_key,
                            ingest_index=index,
                        ),
                        ingest_index=index,
                        received_at=received_at,
                    )
                    for index, item in enumerate(items_to_publish)
                ]
                target_topic = producer.publish_raw_batch(
                    data=events,
                    source="http",
                    serial_number=serial_number,
                )
            else:
                target_topic = producer.publish_raw(
                    data=build_raw_event(
                        items_to_publish[0],
                        source="http",
                        serial_number=serial_number,
                        request_id=request_id,
                        idempotency_key=idempotency_key,
                        ingest_index=0,
                        received_at=received_at,
                    ),
                    source="http",
                    serial_number=serial_number,
                )
        except (
            KafkaProducerError,
            KafkaPublishError,
            KafkaDeliveryError,
            ValueError,
            TypeError,
        ) as exc:
            logger.exception(
                "Kafka publish failed",
                extra={
                    "request_id": request_id,
                    "topic": target_topic or settings.KAFKA_TOPIC_TELEMETRY_RAW,
                    "count": count,
                    "error_type": exc.__class__.__name__,
                },
            )
            return JsonResponse({"error": "Kafka publish failed"}, status=503)

        # Record metrics for ingested messages
        record_telemetry_ingested(count=count, source="http")

        response = TelemetryResponseFormatter.format_async_accepted(
            request_id=request_id,
            task_id="kafka",
            count=count,
            idempotency_key=idempotency_key,
        )
        response["topic"] = target_topic or settings.KAFKA_TOPIC_TELEMETRY_RAW
        response["pipeline_mode"] = settings.TELEMETRY_PIPELINE_MODE
        return JsonResponse(response, status=202)
