from typing import Any
from datetime import datetime
from decimal import Decimal, InvalidOperation
import logging

from django.forms.models import model_to_dict
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

from .models import Telemetry
from apps.devices.models import Device

logger = logging.getLogger(__name__)


SUPPORTED_SCHEMA_VERSIONS = ["1.0"]


class TelemetrySerializer:
    """
    Serializer for Telemetry model.
    Handles validation, normalization, and conversion of telemetry data.
    """

    def __init__(
        self,
        instance: Telemetry | None = None,
        data: dict[str, Any] | None = None,
    ):
        self.instance = instance
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        if not self.instance:
            raise ValueError(
                "TelemetrySerializer(instance=...) is required for to_dict()"
            )

        result = model_to_dict(self.instance, fields=("id", "timestamp", "payload"))
        result["device_id"] = str(self.instance.device.id)
        result["timestamp"] = self.instance.timestamp.isoformat()
        return result

    def _validate_required_fields(self) -> dict[str, str]:
        errors = {}

        if not self.data.get("serial_number"):
            errors["serial_number"] = "This field is required."

        if not self.data.get("schema_version"):
            errors["schema_version"] = "This field is required."

        schema_version = self.data.get("schema_version")
        if schema_version and schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            errors["schema_version"] = (
                f"Unsupported schema version. Supported: {SUPPORTED_SCHEMA_VERSIONS}"
            )

        return errors

    def _get_device(self, serial_number: str) -> Device:
        try:
            return Device.objects.get(serial_number=serial_number)
        except Device.DoesNotExist:
            logger.warning(
                "Device not found",
                extra={"serial_number": serial_number},
                stack_info=False,
            )
            raise ValidationError({"device": "Invalid device"})

    def _normalize_value(self, value: Any) -> float:
        try:
            if isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, str):
                return float(Decimal(value))
            else:
                return value
        except (ValueError, InvalidOperation):
            raise ValidationError({"value": "Invalid numeric value provided."})

    def _parse_timestamp(self, timestamp: Any) -> datetime:
        if isinstance(timestamp, str):
            try:
                parsed_timestamp = parse_datetime(timestamp)
                if parsed_timestamp is None:
                    raise ValueError("Invalid datetime format")
                return parsed_timestamp
            except (ValueError, TypeError):
                raise ValidationError(
                    {"timestamp": "Invalid timestamp format. Use ISO 8601 format."}
                )
        elif isinstance(timestamp, datetime):
            return timestamp
        else:
            raise ValidationError(
                {"timestamp": "Timestamp must be a string or datetime object."}
            )

    def validate(self) -> dict[str, Any]:
        if self.data is None:
            raise ValueError("TelemetrySerializer(data=...) is required for validate()")

        errors = self._validate_required_fields()
        if errors:
            raise ValidationError(errors)

        device = self._get_device(self.data["serial_number"])

        cleaned_payload = {}
        cleaned_payload["schema_version"] = self.data["schema_version"]
        cleaned_payload["serial_number"] = self.data["serial_number"]

        if "value" in self.data:
            value = self._normalize_value(self.data["value"])
            if self.data["schema_version"] == "1.0":
                value = value / 100
            cleaned_payload["value"] = value

        cleaned = {
            "device": device,
            "payload": cleaned_payload,
        }

        if "timestamp" in self.data and self.data["timestamp"]:
            cleaned["timestamp"] = self._parse_timestamp(self.data["timestamp"])

        return cleaned

    def validate_for_bulk(self) -> dict[str, Any]:
        return self.validate()

    def save(self) -> Telemetry:
        cleaned = self.validate()

        if self.instance is None:
            obj = Telemetry(**{k: v for k, v in cleaned.items() if k != "timestamp"})
            if "timestamp" in cleaned:
                obj.timestamp = cleaned["timestamp"]
        else:
            obj = self.instance
            for k, v in cleaned.items():
                setattr(obj, k, v)

        obj.full_clean()
        obj.save()
        return obj
