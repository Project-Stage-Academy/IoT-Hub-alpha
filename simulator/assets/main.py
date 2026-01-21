import requests
from pathlib import Path
from typing import Any
from time import perf_counter
from .data_structures import ParsedArgs
from .helpers import get_data_from_demos
from .senders import HttpSender, MqttSender
from .runner import run_loop
from .reporting import Reporter

def main_sim(raw: Any):
    """
    Main program flow
    
    :param raw: Description
    :type raw: Any
    """
    prog_start = perf_counter()
    parsed_data = ParsedArgs.model_validate(vars(raw))
    
    if parsed_data.devices:
        tasks = parsed_data.devices
    elif parsed_data.files:
        tasks = get_data_from_demos(parsed_data.files)
    else:
        raise ValueError("No Task Found")
    
    if parsed_data.mode.lower() == "http":
        session = requests.Session()
        sender = HttpSender(session=session, base_url=parsed_data.url)
    elif parsed_data.mode.lower() == "mqtt":
        sender = MqttSender(broker_url=parsed_data.url, topic="telemetry")
    else:
        raise ValueError("Mode not recognized")


    if parsed_data.log:
        parent_path = Path(__file__).resolve().parent.parent if parsed_data.log else None
        log_path = Path(f"{parent_path}/{parsed_data.log_file}")
    else:
        log_path = None

    reporter = Reporter(verbose=parsed_data.verbose, log_path=log_path)

    stats = run_loop(
        tasks=tasks,
        sender=sender,
        reporter=reporter,
        rate = parsed_data.rate,
        count = parsed_data.count,
    )
    total_run_time = perf_counter() - prog_start
    reporter.end_report(stats, total_run_time)