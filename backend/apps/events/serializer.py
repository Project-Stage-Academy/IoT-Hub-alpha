from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from django.db import transaction
from django.forms.models import model_to_dict

from .models import Event


class ApiValidationError(Exception):
    def __init__(self, errors: dict[str, Any], status_code: int = 400):
        super().__init__("Validation error")
        self.errors = errors
        self.status_code = status_code


@dataclass
class EventSerializer:
    instance: Optional[Event] = None
    data: Optional[dict[str, Any]] = None
    partial: bool = False

    read_fields = (
        "id",
        "severity",
        "message",
        "status",
        "execution_results",
        "telemetry_snapshot",
    )
    write_fields = ("status",)

    errors: dict[str, Any] = field(default_factory=dict)
    _cached_dict: Optional[dict[str, Any]] = field(default=None, init=False)

    def to_dict(self) -> dict[str, Any]:
        if self._cached_dict is None:
            if self.instance is None:
                raise ValueError(
                    "EventSerializer(instance=...) is required for to_dict()"
                )

            payload = model_to_dict(self.instance, fields=self.read_fields)
            snapshot = payload.get("telemetry_snapshot") or {}
            if not isinstance(snapshot, dict):
                snapshot = {}

            created_at = self.instance.timestamp.isoformat()
            fired_at = snapshot.get("timestamp")
            if not isinstance(fired_at, str) or not fired_at:
                fired_at = created_at

            payload["rule_id"] = str(self.instance.rule_id)
            payload["device_id"] = str(self.instance.rule.device_id)
            payload["fired_at"] = fired_at
            payload["created_at"] = created_at
            payload["acknowledged"] = self.instance.acknowledged
            payload["payload"] = snapshot.get("payload")

            self._cached_dict = payload

        return self._cached_dict

    def validate(self) -> dict[str, Any]:
        if self.data is None:
            raise ValueError("EventSerializer(data=...) is required for validate()")

        cleaned: dict[str, Any] = {}
        required = set(self.write_fields) if not self.partial else set()

        for field_name in required:
            if field_name not in self.data:
                self.errors[field_name] = "This field is required."

        for field_name in self.write_fields:
            if field_name in self.data:
                cleaned[field_name] = self.data.get(field_name)

        self._validate_status(cleaned)

        if self.errors:
            raise ApiValidationError(self.errors, status_code=400)

        return cleaned

    def _validate_status(self, cleaned: dict[str, Any]) -> None:
        if "status" not in cleaned:
            return
        status_value = cleaned.get("status")
        allowed = {choice for choice, _ in Event.EventStatus.choices}
        if status_value not in allowed:
            self.errors["status"] = (
                f"Invalid status. Allowed: {', '.join(sorted(allowed))}"
            )

    @transaction.atomic
    def save(self) -> Event:
        cleaned = self.validate()
        if self.instance is None:
            raise ValueError("EventSerializer(instance=...) is required for save()")

        for key, value in cleaned.items():
            setattr(self.instance, key, value)
        self.instance.full_clean()
        self.instance.save()
        return self.instance
