from pydantic import BaseModel, ConfigDict
from dataclasses import dataclass

class PayloadBase(BaseModel):
    schema_version: str | None = None
    ssn: str | None = None
    value: int | float | None = None

class PayloadExtended(PayloadBase):
    model_config = ConfigDict(extra="allow")

class PayloadEnvelope(BaseModel):
    name: str
    data: PayloadExtended
    expected: int

class Config(BaseModel):
    default_url: str
    default_data_file: list[str]
    log_file: str
    default_timeout: float
    devices: list[PayloadEnvelope]

class SendResult(BaseModel):
    code_got : int | None
    code_expected: int | None
    status: str
    latency: int 
    error: str | None

class ParsedArgs(BaseModel):
    files: list[str] | None
    mode: str
    url: str
    count: int
    rate: float
    devices: list[PayloadEnvelope] | None
    log_file: str
    log: bool
    verbose: bool

@dataclass
class RunStats:
    sent: int = 0
    failed: int = 0
    passed: int = 0
    errors: int = 0