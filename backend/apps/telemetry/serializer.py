from dataclasses import dataclass
from typing import Any
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.forms.models import model_to_dict
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

from .models import Telemetry
from apps.devices.models import Device


@dataclass
class TelemetrySerializer:
    instance: Telemetry | None = None
    data: dict[str, Any] | None = None

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

        if not self.data.get("device_id"):
            errors["device_id"] = "This field is required."

        if not self.data.get("schema_version"):
            errors["schema_version"] = "This field is required."

        if self.data.get("payload") is None:
            errors["payload"] = "This field is required."

        return errors

    def _get_device(self, device_id: str) -> Device:
        try:
            return Device.objects.get(id=device_id)
        except Device.DoesNotExist:
            raise ValidationError(
                {"device_id": f"Device with id '{device_id}' does not exist."}
            )

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

        device = self._get_device(self.data["device_id"])

        cleaned_payload = (
            dict(self.data["payload"]) if isinstance(self.data["payload"], dict) else {}
        )
        cleaned_payload["schema_version"] = self.data["schema_version"]

        if "serial_number" in self.data:
            cleaned_payload["serial_number"] = self.data["serial_number"]

        if "value" in self.data:
            cleaned_payload["value"] = self._normalize_value(self.data["value"])

        cleaned = {
            "device": device,
            "payload": cleaned_payload,
        }

        if "timestamp" in self.data and self.data["timestamp"]:
            cleaned["timestamp"] = self._parse_timestamp(self.data["timestamp"])

        return cleaned

    def validate_for_bulk(self) -> dict[str, Any]:
        cleaned = self.validate()
        prepared = {
            "device": cleaned["device"],
            "payload": cleaned["payload"],
        }
        if "timestamp" in cleaned:
            prepared["timestamp"] = cleaned["timestamp"]
        return prepared

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
