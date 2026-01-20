import json
from pathlib import Path
from datetime import datetime, timezone
from .pydantic_types import SendResult, PayloadEnvelope, RunStats

class Reporter:
    def __init__(self, verbose: bool, log_path: Path | None) -> None:
        self.verbose = verbose
        self.log_path = log_path

    def start_report(self, total_tasks: int | str) -> None:
        total_tasks = "Infinite" if total_tasks == 0 else total_tasks
        print(f"Started runner... total tasks: {total_tasks}")

        if self.log_path:
            start_record: dict[str, str | datetime | int] = {
                "msg": "Starting runner",
                "ts": datetime.now(timezone.utc).isoformat(),
                "total_tasks": total_tasks
            }
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(start_record, ensure_ascii=False) + "\n")

    def report(self, item: PayloadEnvelope, result: SendResult) -> None:
        if self.verbose:
            print(f"{item.name}: code={result.code_got}, expected={result.code_expected} latency={result.latency} ms")

        if self.log_path:
            record: dict[str, int | float | str | datetime | None] = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "device": item.name,
                "status": result.status,
                "expected": item.expected,
                "got": result.code_got,
                "latency": result.latency
            }
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def end_report(self, stats: RunStats, total_run_time: float) -> None:
        pass_rate = (stats.passed / stats.sent) * 100 if stats.sent else 0.0
        print(f"Run ended \n"
              f"Sent: {stats.sent}, passed: {stats.passed}, failed: {stats.failed}\n"
              f"Pass rate = {round(pass_rate, 1)}%, Ran for: {round(total_run_time, 2)} s"
              )
        
        if self.log_path:
            record: dict[str, int | str] = {
                "msg": "Run ended",
                "passed": stats.passed,
                "failed": stats.failed,
                "total": stats.sent
            }
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")