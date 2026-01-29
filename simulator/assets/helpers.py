import argparse
import json
from pathlib import Path
from .data_structures import Config, PayloadEnvelope

def get_data_from_demos(files: list[str]) -> list[PayloadEnvelope]:
    """
    Extracts tasks from demo files
    
    :param files: Description
    :type files: list[str]
    :return: Description
    :rtype: list[PayloadEnvelope]
    """
    root = Path(__file__).resolve().parent.parent
    payloadenvelope: list[PayloadEnvelope] = []
    for file in files:
        path = Path(f"{root}/assets/demos/{file}")
        if not path.exists():
            raise argparse.ArgumentTypeError(f"{file} in config.simulator but does not exist")
        with open(path, "r") as f:
            raw = json.load(f)
        for item in raw:
            payload = PayloadEnvelope.model_validate(item)
            payloadenvelope.append(payload)
    return payloadenvelope

def get_config() -> Config:
    """
    Loads config file
    
    :return: Description
    :rtype: Config
    """
    base = Path(__file__).resolve().parent.parent
    config_path = Path(f"{base}/config.simulator.json")
    with open(config_path, "r") as f:
        raw = json.load(f)
    config = Config.model_validate(raw)
    return config