import json
import argparse
from pathlib import Path
from typing import cast
from .sim_types import Config, ParserArgs, DeviceEntry

def check_devices(devices: list[DeviceEntry]) -> None:
    if len(devices) == 0:
        raise argparse.ArgumentTypeError("Atleast one valid device should be present in sim_config.json")
    
def check_convert_file_path(files: list[str] | list[Path]) -> list[Path]:
    if len(files) == 0:
        raise argparse.ArgumentTypeError("Must provide atleast 1 data file")
    if all(isinstance(file, Path) for file in files):
        return cast(list[Path], files)
    path_files: list[Path] = []
    for file in files:
        file_path = Path(f"../docs/demos/{file}")
        if not file_path.exists():
            raise argparse.ArgumentTypeError(f"{file} not found!")
        path_files.append(file_path)
    return path_files
    

def load_config() -> Config:
    with open("config.simulator.json", "r") as f:
        raw = json.load(f)
    
    config = Config.model_validate(raw)

    check_devices(config.devices)
    config.default_data_file = check_convert_file_path(config.default_data_file)
    return config

def validate_args(args: ParserArgs) -> None:
    print(*args)