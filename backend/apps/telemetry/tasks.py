import logging
from celery import shared_task
from django.core.exceptions import ValidationError
from django.db import transaction

from .serializer import TelemetrySerializer
from .models import Telemetry
from .utils import extract_validation_errors

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def ingest_telemetry_batch_async(self, batch_data: list, request_id: str) -> dict:
    logger.info(
        "Starting async telemetry ingestion",
        extra={"request_id": request_id, "batch_size": len(batch_data)},
    )

    validated_items = []
    errors = []

    for idx, item in enumerate(batch_data):
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
            logger.exception(
                "Unexpected validation error",
                extra={"request_id": request_id, "index": idx},
            )
            errors.append({"index": idx, "error": str(e)})

    if errors:
        logger.error(
            "Batch validation failed",
            extra={
                "request_id": request_id,
                "total": len(batch_data),
                "failed": len(errors),
            },
        )
        return {
            "status": "failed",
            "request_id": request_id,
            "summary": {
                "total": len(batch_data),
                "successful": 0,
                "failed": len(errors),
            },
            "errors": errors,
        }

    try:
        with transaction.atomic():
            telemetry_objects = [
                Telemetry(**validated) for validated in validated_items
            ]
            created = Telemetry.objects.bulk_create(telemetry_objects)

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

    except Exception as e:
        logger.exception(
            "Batch ingestion database error",
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
