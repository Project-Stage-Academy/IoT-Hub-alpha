import logging
from uuid import UUID
from celery import shared_task
from typing import Any
from dataclasses import dataclass
from django.db import OperationalError, InterfaceError
from django.db.utils import DatabaseError
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.db import transaction
from apps.telemetry.models import Telemetry
from apps.telemetry.models import Device
from .services import TelemetryBatchProcessor
from celery.exceptions import MaxRetriesExceededError
from apps.telemetry.service_layer.publish_to_dlq import publish_flush_to_dlq
from apps.telemetry.service_layer.helpers import get_producer


import time


@dataclass
class WriterResult:
    success: bool = True
    written_to_db: int = 0
    written_to_dlq: int = 0

    def to_dict(self):
        return {
            "success": self.success,
            "written_to_db": self.written_to_db,
            "written_to_dlq": self.written_to_dlq,
        }


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def bulk_telemetry_write(self, flush) -> dict[str, Any]:
    producer = get_producer()
    serials = {p.get("device_serial") for p in flush}
    result = WriterResult()
    telem_data = []
    bad_data = []

    try:
        device_by_serial = Device.objects.in_bulk(serials, field_name="serial_number")

        for p in flush:
            d = device_by_serial.get(p.get("device_serial"))
            if not d:
                logger.warning(
                    "Device not in DB", extra={"device": p.get("device_serial")}
                )
                bad_data.append(p)
                continue

            telem_data.append(Telemetry(payload=p.get("payload"), device_id=d.id))

        if bad_data:
            logger.warning("No device id detected", extra={"bad_data": bad_data})

            result.written_to_dlq += len(bad_data)

            publish_flush_to_dlq(producer, bad_data, reason="Wrong device serial")

        if not telem_data:
            logger.info("Nothing to write, Bad batch")
            return result.to_dict()

        logger.info(
            f"Attempting flush of {len(flush)} size, attempt {self.request.retries}",
            extra={"retry_num": self.request.retries, "buffeR_size": len(flush)},
        )

        with transaction.atomic():
            Telemetry.objects.bulk_create(
                telem_data, batch_size=settings.DB_INSERT_BATCH_SIZE
            )
            result.written_to_db += len(telem_data)
            logger.info("Successfully written to DB")

    except (OperationalError, InterfaceError, DatabaseError) as e:
        try:
            logger.warning(
                f"DB Write failed due to: {e}, attempt {self.request.retries}"
            )
            raise self.retry(countdown=60 * (2**self.request.retries))
        except MaxRetriesExceededError:
            logger.warning("DB Write attemps execceded max, dumping batch to telem.dlq")
            if publish_flush_to_dlq(producer, flush, reason="Failed DB Write"):
                result.written_to_dlq += len(flush)
            else:
                result.success = False

    return result.to_dict()


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
