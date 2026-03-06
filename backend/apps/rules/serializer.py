from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.forms.models import model_to_dict

from apps.devices.models import Device

from .exceptions import ApiValidationError
from .models import Rule, validate_condition, validate_action_config


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


@dataclass
class RuleSerializer:
    instance: Optional[Rule] = None

    read_fields = (
        "id",
        "name",
        "description",
        "condition",
        "action_config",
        "is_enabled",
    )

    def to_dict(self) -> dict[str, Any]:
        if self.instance is None:
            raise ValueError("RuleSerializer(instance=...) is required for to_dict()")

        payload = model_to_dict(self.instance, fields=self.read_fields)
        payload["id"] = str(self.instance.id)
        payload["device_id"] = str(self.instance.device_id)

        for k in ("last_triggered_at", "created_at", "updated_at"):
            dt = getattr(self.instance, k, None)
            payload[k] = dt.isoformat() if dt else None

        return payload


@dataclass
class RuleValidator:
    data: Optional[dict[str, Any]] = None
    partial: bool = False
    instance: Optional[Rule] = None

    write_fields = (
        "name",
        "description",
        "condition",
        "action_config",
        "is_enabled",
        "device_id",
    )

    errors: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> dict[str, Any]:
        self.errors = {}
        if self.data is None:
            raise ValueError("RuleValidator(data=...) is required for validate()")
        cleaned = self._parse_and_clean()
        self._validate_business_rules(cleaned)

        if self.errors:
            raise ApiValidationError(self.errors, status_code=400)

        return cleaned

    def _parse_and_clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        self._require_fields()
        self._copy_allowed_fields(cleaned)
        self._normalize_strings(cleaned)
        return cleaned

    def _validate_business_rules(self, cleaned: dict[str, Any]) -> None:
        self._validate_name(cleaned)
        self._validate_condition(cleaned)
        self._validate_action_config(cleaned)
        self._validate_is_enabled(cleaned)
        self._resolve_device(cleaned)

    def _require_fields(self) -> None:
        if self.partial:
            return
        required = {"name", "condition", "action_config", "device_id"}
        for f in required:
            if f not in self.data:
                self.errors[f] = "This field is required."

    def _copy_allowed_fields(self, cleaned: dict[str, Any]) -> None:
        for k in self.write_fields:
            if k in self.data:
                cleaned[k] = self.data.get(k)

    def _normalize_strings(self, cleaned: dict[str, Any]) -> None:
        for k in ("name", "description"):
            if k in cleaned and isinstance(cleaned[k], str):
                cleaned[k] = cleaned[k].strip()

    def _validate_name(self, cleaned: dict[str, Any]) -> None:
        if "name" in cleaned and _is_blank(cleaned["name"]):
            self.errors["name"] = "Rule name cannot be blank."

    def _validate_condition(self, cleaned: dict[str, Any]) -> None:
        if "condition" not in cleaned:
            return
        try:
            validate_condition(cleaned["condition"])
        except DjangoValidationError as e:
            self.errors["condition"] = e.message

    def _validate_action_config(self, cleaned: dict[str, Any]) -> None:
        if "action_config" not in cleaned:
            return
        try:
            validate_action_config(cleaned["action_config"])
        except DjangoValidationError as e:
            self.errors["action_config"] = e.message

    def _validate_is_enabled(self, cleaned: dict[str, Any]) -> None:
        if "is_enabled" in cleaned:
            if not isinstance(cleaned["is_enabled"], bool):
                self.errors["is_enabled"] = "is_enabled must be a boolean."

    def _resolve_device(self, cleaned: dict[str, Any]) -> None:
        if "device_id" not in cleaned:
            return
        device_id = cleaned["device_id"]
        try:
            if isinstance(device_id, str):
                UUID(device_id)
            device = Device.objects.get(id=device_id)
            cleaned["device"] = device
        except (ValueError, Device.DoesNotExist):
            self.errors["device_id"] = "Device not found or invalid id."
        else:
            cleaned.pop("device_id", None)


class RuleRepository:
    @staticmethod
    @transaction.atomic
    def save(cleaned: dict[str, Any], instance: Optional[Rule] = None) -> Rule:
        if instance is None:
            obj = Rule(**cleaned)
        else:
            obj = instance
            for k, v in cleaned.items():
                setattr(obj, k, v)

        obj.full_clean()
        obj.save()
        return obj
