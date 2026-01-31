from pydantic import BaseModel, ConfigDict, model_validator
from datetime import datetime
from typing import Literal
from uuid import UUID


class AggregateStructure(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    values: list[float]
    rule_id: UUID
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
