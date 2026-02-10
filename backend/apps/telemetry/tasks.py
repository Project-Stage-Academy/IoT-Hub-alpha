import logging
from uuid import UUID

from celery import shared_task
from django.db import OperationalError, InterfaceError
from django.db.utils import DatabaseError
from django.utils.dateparse import parse_datetime

from .services import TelemetryBatchProcessor

logger = logging.getLogger(__name__)


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
