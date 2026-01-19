from pydantic import BaseModel, ConfigDict

class PayloadBase(BaseModel):
    schema_version: str | None = None
    ssn: str | None = None
    value: int | None = None

class PayloadExtended(PayloadBase):
    model_config = ConfigDict(extra="allow")

class PayloadEnvelope(BaseModel):
    name: str
    data: PayloadExtended
    expected: int

class Config(BaseModel):
    default_url: str
    default_data_file: list[str]
    devices: list[PayloadEnvelope]