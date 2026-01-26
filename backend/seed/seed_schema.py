from pydantic import BaseModel
from decimal import Decimal
from typing import Any
from dataclasses import dataclass, field


class DeviceTypeSeed(BaseModel):
    name: str
    description: str = ""
    metric_name: str
    metric_unit: str
    metric_min: Decimal
    metric_max: Decimal

class DeviceSeed(BaseModel):
    serial_number: str
    name: str
    device_type: str
    location: str = ""
    status: str = "active"

class ActionConfig(BaseModel):
    type: str
    template_id: str | int | None = None
    recipients: list[str] | None = None
    machine_id: str | None = None


class RuleSeed(BaseModel):
    name: str
    device: str
    comparison_operator: str
    description: str
    threshold: Decimal
    action_config: list[ActionConfig]
    is_enabled: bool

class NotificationTemplateSeed(BaseModel):
    name: str
    message_template: str
    recipients: list[dict[Any, Any]]
    priority: int
    retry_count: int
    retry_delay_minutes: int
    is_active: bool

class Payload(BaseModel):
    schema_version: str
    value: int | float

class TelemetrySeed(BaseModel):
    device: str
    payload: Payload

class SeedData(BaseModel):
    device_types: list[DeviceTypeSeed]
    devices: list[DeviceSeed]
    rules: list[RuleSeed]
    telemetry: list[TelemetrySeed]
    notification_templates: list[NotificationTemplateSeed]

@dataclass
class Stats:
    updated: int = 0
    created: int = 0

    def add(self, *, created: bool) -> None:
        if created:
            self.created += 1
        else:
            self.updated += 1

@dataclass
class StatsTally:
    device_types: Stats = field(default_factory=Stats)
    devices: Stats = field(default_factory=Stats)
    rules: Stats = field(default_factory=Stats)
    notification_templates: Stats = field(default_factory=Stats)
    telemetry: Stats = field(default_factory=Stats)