import json
import argparse
from pathlib import Path
from .sim_types import Config, ParserArgs, DeviceEntry

def check_devices(devices: list[DeviceEntry]) -> None:
    if len(devices) == 0:
        raise argparse.ArgumentTypeError("Atleast one valid device should be present in sim_config.json")
    
def check_convert_file_path(file: str | None) -> Path | None:
    if not file:
        return None
    if len(file) == 0:
        raise argparse.ArgumentTypeError("Must provide atleast 1 data file")
    file_path = Path(f"../docs/demos/{file}")
    if not file_path.exists():
        raise argparse.ArgumentTypeError(f"{file} not found!")
    return file_path

def get_name(file: str | None, device: DeviceEntry | None) -> str:
    if file:
        return file
    return device.device_name

def load_config() -> Config:
    with open("config.simulator.json", "r") as f:
        raw = json.load(f)
    
    config = Config.model_validate(raw)

    check_devices(config.devices)
    return config

def validate_args(args: ParserArgs) -> None:
    print(*args)