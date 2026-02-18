from pydantic import BaseModel, Field, field_validator
from typing import Literal


class TelemetrySchema(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    serial_number: str = Field(pattern=r"^[A-Z]+-SN-\d{3}$")
    value: int = Field(ge=0)

    @field_validator("schema_version")
    def check_schema_version(cls, v):
        if v != "1.0":
            raise ValueError(f"Unsupported schema version {v}! Expected 1.0")
        else:
            return v
