from pydantic import BaseModel, ConfigDict

class PayloadBase(BaseModel):
    json_version: float
    ssn: str
    value: int

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