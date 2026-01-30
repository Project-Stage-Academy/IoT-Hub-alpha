from pydantic import BaseModel, UUID4, ConfigDict, model_validator
from datetime import datetime
from typing import Literal
from apps.rules.models import Rule

class AggregateStructure(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    values: list[float]
    rule: Rule
    start: datetime
    end: datetime
    
class ActionConfig():
    type: str
    recipients: str | None = None
    url: str | None = None
    url: str | None = None
    template_id: int

class NormalizedRecipient(BaseModel):
    type: Literal["sms", "email", "webhook"]
    target: str
    name: str | None = None

    @model_validator(mode="before")
    @classmethod
    def derive_target(cls, data):
        # data is the raw input (usually a dict)
        if not isinstance(data, dict):
            return data

        t = data.get("type")
        key_map = {"sms": "phone", "email": "address", "webhook": "url"}

        key = key_map.get(t)
        if not key:
            return data  # let Pydantic raise "invalid literal" for type

        if "target" not in data:
            if key not in data:
                raise ValueError(f"Missing '{key}' for type '{t}'")
            data = {**data, "target": data[key]}

        return data