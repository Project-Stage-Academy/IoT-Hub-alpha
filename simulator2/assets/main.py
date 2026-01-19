from typing import Any
import requests
import time
from .pydantic_types import PayloadEnvelope
from .helpers import get_data_from_demos


class MainSim():
    def __init__(self, raw: Any,  data: PayloadEnvelope) -> None:
        self.name = data.name
        self.payload = data.data
        self.expected = data.expected
        self.count = raw.count
        self.rate = raw.rate
        self.url = raw.url
        self.mode = raw.mode
        self.log = raw.log

    def http_protocol(self, current: int, total_tasks: int) -> None:
        r = requests.post(self.url, json=self.payload.model_dump())
        print(f"Got: {r.status_code}, Expected: {self.expected}\n"
              f"Task {current + 1}/{total_tasks}")
        time.sleep(self.rate)

    @staticmethod
    def create_tasks(raw: Any) -> None:
        if raw.devices:
            data: list[PayloadEnvelope] = raw.devices
        else:
            data: list[PayloadEnvelope] = get_data_from_demos(raw.files)
        tasks: list[MainSim] = []
        for telem in data:
            instance = MainSim(raw, telem)
            tasks.append(instance)
        for idx, task in enumerate(tasks):
            task.http_protocol(idx, len(tasks))

    def __str__(self):
        return (f"name={self.name}, count={self.count}, rate={self.rate}, url={self.url}, mode={self.mode}\n"
                   f"payload={self.payload}\n"
                   f"Writing to log.txt={self.log}"
        )
