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

class Config(BaseModel):
    default_url: str
    default_data_file: list[str] | list[Path]
    devices: list[DeviceEntry]

class ParserArgs(BaseModel):
    files: list[Path]
    mode: str
    url: str
    count: int
    rate: int
    devices: list[DeviceEntry]
