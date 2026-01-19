#import asyncio
import json
import argparse
from .sim_types import DeviceEntry, ParserArgs, FileTelemetry
from .helpers import check_convert_file_path, get_name
from .request_actual import RequestActual

class MainSend(RequestActual):
    def __init__(self, data: ParserArgs, file: str | None = None, device: DeviceEntry | None = None) -> None:
        self.name = get_name(file, device)
        self.file = check_convert_file_path(file)
        self.mode = data.mode
        self.url = data.url
        self.count = data.count
        self.rate = data.rate
        self.device = device
        self.telemetry = []

    def setup_demo(self):
        if not self.file:
            raise argparse.ArgumentTypeError("Something went wrong with opening the file!")
        with open(self.file, "r") as f:
            raw = json.load(f)
        file_payload = FileTelemetry.model_validate(raw)
        self.count = file_payload.count
        self.rate = file_payload.rate
        self.telemetry = file_payload.telemetry_data
        

    def setup_device(self):
        if not self.device:
            raise argparse.ArgumentTypeError("Something went wrong with fetching device info!")

    @staticmethod
    def run_sim(data: ParserArgs) -> None:
        payloads: list[MainSend] = []
        if data.devices:
            for device in data.devices:
                payload_instance = MainSend(data, file=None, device=device)
                payload_instance.setup_device()
                payloads.append(payload_instance)
        elif data.files:
            for file in data.files:
                payload_instance = MainSend(data, file=file, device=None)
                payload_instance.setup_demo()
                payloads.append(payload_instance)