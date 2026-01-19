from typing import Any
from .pydantic_types import PayloadEnvelope
from .helpers import get_data_from_demos


class MainSim():
    def __init__(self, raw: Any,  data: PayloadEnvelope) -> None:
        self.name = data.name
        self.payload = data.data
        self.count = raw.count
        self.rate = raw.rate
        self.url = raw.url
        self.mode = raw.mode

    @staticmethod
    def create_tasks(raw: Any):
        if raw.devices:
            data: list[PayloadEnvelope] = raw.devices
        else:
            data: list[PayloadEnvelope] = get_data_from_demos(raw.files)
        tasks: list[MainSim] = []
        for telem in data:
            instance = MainSim(raw, telem)
            tasks.append(instance)
        for task in tasks:
            print (task)

    def __str__(self):
        return (f"name={self.name}, count={self.count}, rate={self.rate}, url={self.url}, mode={self.mode}\n"
                   f"payload={self.payload}"
        )
