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

from .tasks import ingest_telemetry_batch_async
from .producers import build_raw_event, get_producer
from .services import (
    TelemetryValidator,
    TelemetryBatchProcessor,
    TelemetryResponseFormatter,
)

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


@method_decorator(csrf_exempt, name="dispatch")
class TelemetryIngestView(View):
    """
    POST /api/v1/telemetry/ — publish raw telemetry to the producer.

    Accepts single or batched payloads, wraps each item in a
    ``telemetry.raw`` envelope and hands it to the configured
    :class:`~apps.telemetry.producers.TelemetryProducer`.

    Validation and persistence are handled downstream by the
    Kafka consumer (separate story).
    """

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
        else:
            data["serial_number"] = serial_number
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
            return self._handle_sync(data, is_batch, idempotency_key, serial_number)

    def _handle_sync(
        self,
        data,
        is_batch: bool,
        idempotency_key: str | None,
        serial_number: str,
    ):
        if is_batch:
            for item in data:
                item["serial_number"] = serial_number
        else:
            data["serial_number"] = serial_number

        # Publish raw payload(s) to telemetry.raw topic
        producer = get_producer()
        items_to_publish = data if is_batch else [data]
        for item in items_to_publish:
            producer.publish_raw(
                data=build_raw_event(item, source="http", serial_number=serial_number),
                source="http",
                serial_number=serial_number,
            )

        count = len(items_to_publish)
        response = {"status": "accepted", "count": count}
        if idempotency_key:
            response["idempotency_key"] = idempotency_key
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
                        idempotency_key=idempotency_key,
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
        except Exception as exc:
            logger.exception(
                "Kafka publish failed",
                extra={
                    "request_id": request_id,
                    "topic": target_topic or settings.KAFKA_TOPIC_TELEMETRY_RAW,
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
        response["topic"] = target_topic or settings.KAFKA_TOPIC_TELEMETRY_RAW
        response["pipeline_mode"] = settings.TELEMETRY_PIPELINE_MODE
        return JsonResponse(response, status=202)
