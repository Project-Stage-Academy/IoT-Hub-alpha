from pydantic import BaseModel
from typing import Any


class FakeRule(BaseModel):
    id: str
    action_config: list[dict[str, Any]]
    event_cooldown_until: int
