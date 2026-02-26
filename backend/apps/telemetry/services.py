"""
Service layer for telemetry ingestion.
Separates business logic from view layer for better maintainability.
"""

import logging
from functools import lru_cache
from typing import Any
from django.core.exceptions import ValidationError
from django.db import transaction
from jsonschema import validate
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from .serializer import TelemetrySerializer
from .models import Telemetry
from .models import TelemetrySchema

logger = logging.getLogger(__name__)


def extract_validation_errors(error: ValidationError) -> dict:
    """Extract error details from ValidationError in consistent format."""
    return (
        error.message_dict if hasattr(error, "message_dict") else {"error": str(error)}
    )


def apply_transformations(data: dict, rules: dict) -> dict:
    """
    Apply transformations based on provided rules
    """
    result = data.copy()

    rename_rules = rules.get("rename", {})
    if rename_rules:
        intermediate_map = {}
        for old_key, new_key in rename_rules.items():
            if old_key in result:
                intermediate_map[new_key] = result.pop(old_key)

        result.update(intermediate_map)

    for key, factor in rules.get("multiply", {}).items():
        if key in result and isinstance(result[key], (int, float)):
            result[key] = result[key] * factor

    for key, divisor in rules.get("divide", {}).items():
        if key in result and isinstance(result[key], (int, float)):
            if divisor != 0:
                result[key] = result[key] / divisor

    for key, decimals in rules.get("round", {}).items():
        if key in result and isinstance(result[key], (int, float)):
            result[key] = round(result[key], decimals)

    for key, remover in rules.get("remove", {}).items():
        if key in result and remover:
            result.pop(key, None)

    return result


@lru_cache(maxsize=128)
def _get_schema_cached(version: str):
    return TelemetrySchema.objects.get(version=version, is_active=True)


def get_cached_telemetry_schema(version: str):
    try:
        return _get_schema_cached(version)
    except TelemetrySchema.DoesNotExist:
        return None


def process_telemetry_payload(raw_payload: dict):
    """
    Main pipeline for processing incoming telemetry payload.
    """
    schema_version = raw_payload.get("schema_version")
    if not schema_version:
        return None, "Missing field 'schema_version' in payload"

    schema_obj = get_cached_telemetry_schema(schema_version)

    if not schema_obj:
        return None, f"Active version schema '{schema_version}' not found in database"

    try:
        validate(instance=raw_payload, schema=schema_obj.validation_schema)
    except JsonSchemaValidationError as e:
        error_msg = f"Validation error: field {e.json_path} -> {e.message}"
        return None, error_msg

    try:
        clean_data = apply_transformations(raw_payload, schema_obj.transformation_rules)
        return clean_data, None
    except Exception as e:
        return None, f"Error applying transformations: {str(e)}"


class TelemetryValidator:
    """Handles validation of single or batch telemetry data."""

    @staticmethod
    def _handle_validation_error(
        error: Exception, index: int | None = None
    ) -> dict[str, Any]:
        """Format validation error into consistent structure."""
        if isinstance(error, ValidationError):
            details = extract_validation_errors(error)
            error_dict = {
                "error": "Validation failed",
                "details": details,
            }
            logger.warning(
                "Telemetry validation failed",
                extra={
                    "index": index,
                    "validation_details": details,
                },
            )
        else:
            error_dict = {
                "error": "Invalid data format",
                "details": str(error),
            }
            logger.error(
                "Invalid data format in batch item",
                extra={
                    "index": index,
                    "error": str(error),
                },
            )

        if index is not None:
            error_dict["index"] = index

        return error_dict

    @staticmethod
    def validate_single(data: dict) -> tuple[dict | None, dict | None]:
        """
        Validate single telemetry record.

        Returns:
            tuple: (validated_data, error) - one will be None
        """
        try:
            serializer = TelemetrySerializer(data=data)
            validated = serializer.validate_for_bulk()
            return validated, None
        except (ValidationError, ValueError, TypeError, KeyError) as e:
            return None, TelemetryValidator._handle_validation_error(e)

    @staticmethod
    def validate_batch(data: list) -> tuple[list, list]:
        """
        Validate batch of telemetry records.

        Returns:
            tuple: (validated_items, errors)
        """
        validated_items = []
        errors = []

        for idx, item in enumerate(data):
            try:
                serializer = TelemetrySerializer(data=item)
                validated = serializer.validate_for_bulk()
                validated_items.append(validated)
            except (ValidationError, ValueError, TypeError, KeyError) as e:
                errors.append(TelemetryValidator._handle_validation_error(e, idx))

        return validated_items, errors


class TelemetryBatchProcessor:
    """Handles batch processing and persistence of telemetry data."""

    @staticmethod
    def process_single(validated_data: dict) -> Telemetry:
        """
        Persist single validated telemetry record.

        Args:
            validated_data: Already validated telemetry data

        Returns:
            Created Telemetry instance
        """
        with transaction.atomic():
            return Telemetry.objects.create(**validated_data)

    @staticmethod
    def process_batch(validated_items: list) -> list[Telemetry]:
        """
        Persist batch of validated telemetry records atomically.

        Args:
            validated_items: List of already validated telemetry data

        Returns:
            List of created Telemetry instances
        """
        with transaction.atomic():
            telemetry_objects = [
                Telemetry(**validated) for validated in validated_items
            ]
            return Telemetry.objects.bulk_create(telemetry_objects)


class TelemetryResponseFormatter:
    """Formats API responses for telemetry operations."""

    @staticmethod
    def format_single_created(
        telemetry: Telemetry, idempotency_key: str | None = None
    ) -> dict[str, Any]:
        """Format response for single record creation."""
        response = {
            "status": "created",
            "id": telemetry.id,
            "device_id": str(telemetry.device.id),
            "timestamp": telemetry.timestamp.isoformat(),
        }
        if idempotency_key:
            response["idempotency_key"] = idempotency_key
        return response

    @staticmethod
    def format_batch_created(
        created: list[Telemetry],
        total: int,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Format response for batch creation."""
        created_ids = [obj.id for obj in created]
        response = {
            "status": "created",
            "count": len(created_ids),
            "ids": created_ids,
            "summary": {
                "total": total,
                "successful": len(created_ids),
                "failed": 0,
            },
        }
        if idempotency_key:
            response["idempotency_key"] = idempotency_key
        return response

    @staticmethod
    def format_validation_error(
        errors: list, total: int, is_batch: bool = False
    ) -> dict[str, Any]:
        """Format validation error response."""
        error_message = "Batch ingestion failed" if is_batch else "Validation failed"
        return {
            "error": error_message,
            "details": {
                "summary": {
                    "total": total,
                    "successful": 0,
                    "failed": len(errors),
                },
                "errors": errors,
            },
        }

    @staticmethod
    def format_async_accepted(
        request_id: str,
        task_id: str,
        count: int,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Format response for async ingestion acceptance."""
        response = {
            "status": "accepted",
            "request_id": request_id,
            "count": count,
            "task_id": task_id,
        }
        if idempotency_key:
            response["idempotency_key"] = idempotency_key
        return response
