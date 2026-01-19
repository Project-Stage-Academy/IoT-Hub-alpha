import requests
from itertools import count
from typing import Any
from dataclasses import dataclass
from time import perf_counter, sleep
from .pydantic_types import PayloadEnvelope, PayloadExtended
from .helpers import get_data_from_demos

@dataclass(frozen=True)
class PayloadData:
    name: str
    payload: PayloadExtended
    expected: int

class MainSim():
    def __init__(self, raw: Any) -> None:
        self.session = requests.Session()
        self.count = raw.count
        self.verbose = raw.verbose
        self.rate = raw.rate
        self.url = raw.url
        self.mode = raw.mode
        self.log = raw.log
        self.failed_tasks = 0

    def build_items(self, envelopes: list[PayloadEnvelope]) -> list[PayloadEnvelope]:
        return [
            PayloadEnvelope(name=e.name, data=e.data, expected=e.expected)
            for e in envelopes
        ]

    def send_http_payload(self, payloadEnv: PayloadEnvelope) -> tuple[int | None, int | None, float]:
        start = perf_counter()

        try:
            response = self.session.post(
                self.url,
                json=payloadEnv.data.model_dump(),
                timeout=5.0
            )
            if response.status_code != payloadEnv.expected:
                self.failed_tasks += 1
            latency = perf_counter() - start
            return(response.status_code, payloadEnv.expected, latency)
        
        except requests.RequestException as exc:
            latency = perf_counter() - start
            self.failed_tasks += 1

            print(f"[ERROR] Request failed: {exc}")
            return None, None, latency
        
        finally:
            sleep(self.rate)
    
    def print_to_console(self, total_tasks: int, current_task_num: int, s_code: int | None, expected_code: int | None, latency: float):
        print (f"Task {current_task_num}/{total_tasks} E:{expected_code} G:{s_code} S:{"PASS" if s_code == expected_code else "FAIL"} Latency: {round(latency*1000)} ms")
            

    def log_to_file(self, total_tasks: int, current_task_num: int, s_code: int | None, expected_code: int | None, latency: float):
        pass

    def runner(self, tasks: list[PayloadEnvelope]):
        iterator = range(self.count) if self.count else count(0)
        total_tasks = (len(tasks) * self.count) if self.count else -1
        print(f"Simulator online, Total tasks to process: {total_tasks}")
        for idx in iterator:
            pow_of_iter = idx * len(tasks)
            for current_task_num, task in enumerate(tasks):
                current_task_num = pow_of_iter + 1 + current_task_num
                s_code, expected_code, latency = self.send_http_payload(task)
                if self.verbose:
                    self.print_to_console(total_tasks, current_task_num, s_code, expected_code, latency)
                if self.log:
                    self.log_to_file(total_tasks, current_task_num, s_code, expected_code, latency)
        print (f"All tasks ended, Passed: {total_tasks-self.failed_tasks}/{total_tasks} Pass rate: {round((100*(total_tasks-self.failed_tasks))/total_tasks, 2)}%")

    @staticmethod
    def create_tasks(raw: Any) -> None:
        top = MainSim(raw)
        if raw.devices:
            data: list[PayloadEnvelope] = raw.devices
        else:
            data: list[PayloadEnvelope] = get_data_from_demos(raw.files)
        tasks = top.build_items(data)
        top.runner(tasks)