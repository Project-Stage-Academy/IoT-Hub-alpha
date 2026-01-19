from pydantic import BaseModel, ConfigDict
from pathlib import Path

class DeviceDataMin(BaseModel):
    json_version: float
    ssn: str
    value: int

class DeviceDataExpanded(DeviceDataMin):
    model_config = ConfigDict(extra="allow")

class DeviceEntry(BaseModel):
    device_name: str
    data: DeviceDataExpanded

class DeviceDemo(BaseModel):
    data: DeviceDataExpanded
    expected: int

class Config(BaseModel):
    default_url: str
    default_data_file: list[str] | list[Path]
    devices: list[DeviceEntry]

class TelemetryConfig(BaseModel):
    rate: int
    count: int
    telemetry_data: list[DeviceDemo]


class FileTelemetry(BaseModel):
    rate: int
    count: int
    telemetry_data: list[DeviceDemo]

class ParserArgs(BaseModel):
    files: list[str]
    mode: str
    url: str
    count: int
    rate: int
    devices: list[DeviceEntry] | None
