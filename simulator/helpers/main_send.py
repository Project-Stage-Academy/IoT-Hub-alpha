#import asyncio
import json
from collections import defaultdict
from .sim_types import ParserArgs, DeviceDataExpanded

class MainSend():
    def __init__(self, data: ParserArgs) -> None:
        self.files = data.files
        self.mode = data.mode
        self.url = data.url
        self.count = data.count
        self.rate = data.rate
        self.devices = data.devices
        self.telemetry: dict[int, list[DeviceDataExpanded]] = defaultdict(list)

    def prase_demos(self):
        for file in self.files:
            if file.exists():
                with open(file, "r") as f:
                    raw = json.load(f)
                delay = raw["rate"]
                self.telemetry[delay].extend(
                DeviceDataExpanded.model_validate(d) for d in raw["telemetry_data"]
                )

    @classmethod
    def run_sim(cls, data: ParserArgs) -> None:
        instance = cls(data)
        instance.prase_demos()
        print(instance.telemetry[30])