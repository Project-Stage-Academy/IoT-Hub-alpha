from pydantic import BaseModel, ConfigDict, model_validator, Field
from datetime import datetime
from typing import Literal, Annotated
from uuid import UUID


class AggregateStructure(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    values: list[float]
    rule_id: UUID
    device: UUID
    start: datetime
    end: datetime


class ActionConfig(BaseModel):
    type: Literal["notification", "stop_machine"]
    recipients: list[str] | None = None
    template_id: int | None = None


class NormalizedRecipient(BaseModel):
    type: Literal["sms", "email", "webhook"]
    target: str
    name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def derive_target(cls, data: dict[str, str]) -> dict[str, str]:

        t: str | None = data.get("type")
        key_map = {"sms": "phone", "email": "address", "webhook": "url"}

        key = key_map.get(t)
        if not key:
            return data  # let Pydantic raise "invalid literal" for type

        if "target" not in data:
            if key not in data:
                raise ValueError(f"Missing '{key}' for type '{t}'")
            data = {**data, "target": data[key]}

        return data


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["leaf", "and", "or"]

    operator: Literal["gt", "gte", "lt", "lte", "eq", "ne"] | None = None
    threshold: float | None = None

    window_seconds: int | None = Field(default=None, ge=1)
    occurrences: int | None = Field(default=None, ge=1)

    conditions: list["Condition"] | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> "Condition":
        if self.type == "leaf":
            if self.conditions is not None:
                raise ValueError("leaf node cannot have conditions")
            if self.operator is None or self.threshold is None:
                raise ValueError("leaf node requires operator and threshold")
        else:  # and/or
            if not self.conditions:
                raise ValueError(f"{self.type} node requires non-empty conditions")
            if self.operator is not None or self.threshold is not None:
                raise ValueError(f"{self.type} node cannot have operator/threshold")

        if (self.occurrences is None) != (self.window_seconds is None):
            raise ValueError("occurrences and window_seconds must be set together")

        return self