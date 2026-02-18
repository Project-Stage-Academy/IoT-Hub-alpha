import json
import logging
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from .producers import get_producer, build_raw_event

logger = logging.getLogger(__name__)


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

        idempotency_key = request.headers.get("Idempotency-Key")
        is_batch = isinstance(data, list)

        if is_batch and len(data) == 0:
            return JsonResponse({"error": "Empty batch provided"}, status=400)

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

        # Inject serial_number into every item
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
