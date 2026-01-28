from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.forms.models import model_to_dict

from .models import Device, DeviceType


class ApiValidationError(Exception):

    def __init__(self, errors: dict[str, Any], status_code: int = 400):
        super().__init__("Validation error")
        self.errors = errors
        self.status_code = status_code


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


@dataclass
class DeviceTypeSerializer:
    instance: DeviceType

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.instance.id),
            "name": self.instance.name,
        }


@dataclass
class DeviceSerializer:
    instance: Optional[Device] = None
    data: Optional[dict[str, Any]] = None
    partial: bool = False 

    read_fields = (
        "id",
        "name",
        "serial_number",
        "location",
        "status",
        "last_seen",
        "created_at",
        "updated_at",
    )
    write_fields = (
        "name",
        "serial_number",
        "location",
        "status",
        "device_type_id", 
    )

    errors: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        if not self.instance:
            raise ValueError("DeviceSerializer(instance=...) is required for to_dict()")

        payload = model_to_dict(self.instance, fields=self.read_fields)
        payload["id"] = str(self.instance.id)

        # device_type віддаємо як обʼєкт + id (зручно клієнту)
        payload["device_type"] = DeviceTypeSerializer(self.instance.device_type).to_dict()
        payload["device_type_id"] = str(self.instance.device_type_id)

        # datetimes -> ISO
        for k in ("last_seen", "created_at", "updated_at"):
            dt = getattr(self.instance, k, None)
            payload[k] = dt.isoformat() if dt else None

        return payload

    def validate(self) -> dict[str, Any]:
        if self.data is None:
            raise ValueError("DeviceSerializer(data=...) is required for validate()")

        cleaned: dict[str, Any] = {}

        # 1) Required fields logic
        required = {"name", "serial_number", "device_type_id"}
        for f in required:
            if not self.partial and f not in self.data:
                self.errors[f] = "This field is required."

        # 2) Copy allowed fields
        for k in self.write_fields:
            if k in self.data:
                cleaned[k] = self.data.get(k)

        # 3) Normalize strings
        if "name" in cleaned and isinstance(cleaned["name"], str):
            cleaned["name"] = cleaned["name"].strip()

        if "serial_number" in cleaned and isinstance(cleaned["serial_number"], str):
            cleaned["serial_number"] = cleaned["serial_number"].strip()

        if "location" in cleaned and isinstance(cleaned["location"], str):
            cleaned["location"] = cleaned["location"].strip()

        # 4) Field validation
        if "name" in cleaned and _is_blank(cleaned["name"]):
            self.errors["name"] = "Device name cannot be blank."

        if "serial_number" in cleaned and _is_blank(cleaned["serial_number"]):
            self.errors["serial_number"] = "Serial number cannot be blank."

        # 5) Status choices validation (якщо передали)
        if "status" in cleaned:
            allowed = {c[0] for c in Device._meta.get_field("status").choices}
            if cleaned["status"] not in allowed:
                self.errors["status"] = f"Invalid status. Allowed: {', '.join(sorted(allowed))}"

        # 6) device_type_id -> DeviceType instance
        if "device_type_id" in cleaned:
            dt_id = cleaned["device_type_id"]
            try:
                if isinstance(dt_id, str):
                    UUID(dt_id)
                device_type = DeviceType.objects.get(id=dt_id)
                cleaned["device_type"] = device_type
            except (ValueError, ObjectDoesNotExist):
                self.errors["device_type_id"] = "DeviceType not found or invalid id."
            finally:
                cleaned.pop("device_type_id", None)

        if self.errors:
            raise ApiValidationError(self.errors, status_code=400)

        return cleaned

    @transaction.atomic
    def save(self) -> Device:
        cleaned = self.validate()

        if self.instance is None:
            obj = Device(**cleaned)
        else:
            obj = self.instance
            for k, v in cleaned.items():
                setattr(obj, k, v)

        # Важливо: full_clean() запускає model validation (max_length, choices, unique і т.д.)
        obj.full_clean()
        obj.save()
        return obj
