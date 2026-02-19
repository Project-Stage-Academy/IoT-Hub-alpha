import logging
from uuid import UUID
from celery import shared_task
from django.db import OperationalError, InterfaceError
from django.db.utils import DatabaseError
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.db import transaction
from apps.telemetry.models import Telemetry
from apps.telemetry.models import Device
from .services import TelemetryBatchProcessor
from celery.exceptions import MaxRetriesExceededError
from apps.telemetry.sevice_layer.publish_to_dlq import publish_flush_to_dlq
from apps.telemetry.sevice_layer.kafka_producer import get_producer




logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def bulk_telemetry_write(self, flush):
    producer = get_producer()
    serials = {p.get('device_serial') for p in flush}
    device_by_serial = Device.objects.in_bulk(serials, field_name="serial_number")
        
    telem_data = []
    for p in flush:
        d = device_by_serial.get(p.get('device_serial'))
        if not d:
            raise KeyError(f"Device not in DB: {d}")
        telem_data.append(Telemetry(payload=p.get('payload'), device_id=d.id))
        
    try:
        with transaction.atomic():
            Telemetry.objects.bulk_create(telem_data, batch_size=settings.DB_WRITER_BATCH_SIZE)
    except Exception as e:
        try:
            raise self.retry(exc=e, countdown=60 * (2**self.request.retries))
        except MaxRetriesExceededError:
            publish_flush_to_dlq(producer, flush, reason="Failed DB Write")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def ingest_telemetry_batch_async(self, batch_data: list, request_id: str) -> dict:
    """
    Persist pre-validated telemetry data to database.

    Note: Validation already performed in view before queueing.
    This task focuses on atomic DB persistence with retry logic for transient errors.
    """
    logger.info(
        "Starting async telemetry ingestion",
        extra={"request_id": request_id, "batch_size": len(batch_data)},
    )

    for item in batch_data:
        item["device_id"] = UUID(item["device_id"])
        if "timestamp" in item:
            item["timestamp"] = parse_datetime(item["timestamp"])

    try:
        created = TelemetryBatchProcessor.process_batch(batch_data)

        created_ids = [obj.id for obj in created]

        logger.info(
            "Batch ingestion successful",
            extra={
                "request_id": request_id,
                "count": len(created_ids),
            },
        )

        return {
            "status": "completed",
            "request_id": request_id,
            "count": len(created_ids),
            "ids": created_ids,
            "summary": {
                "total": len(batch_data),
                "successful": len(created_ids),
                "failed": 0,
            },
        }

    except (OperationalError, InterfaceError, DatabaseError) as exc:
        logger.warning(
            "Transient database error, retrying",
            extra={
                "request_id": request_id,
                "retry_count": self.request.retries,
                "error": str(exc),
            },
        )
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))

    except Exception as e:
        logger.exception(
            "Batch ingestion non-retryable error",
            extra={"request_id": request_id},
        )
        return {
            "status": "failed",
            "request_id": request_id,
            "error": str(e),
            "summary": {
                "total": len(batch_data),
                "successful": 0,
                "failed": len(batch_data),
            },
        }
