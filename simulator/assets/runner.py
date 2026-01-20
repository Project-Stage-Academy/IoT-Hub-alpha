from typing import Sequence
from time import sleep
from .senders import Sender
from .reporting import Reporter
from .data_structures import PayloadEnvelope, RunStats

def run_loop(
        tasks: Sequence[PayloadEnvelope],
        sender: Sender,
        reporter: Reporter,
        rate: float,
        count: int,
        ) -> RunStats:
    """
    Runner loop, responsible for running tasks and keeping track of tasks ran.
    
    :param tasks: Description
    :type tasks: Sequence[PayloadEnvelope]
    :param sender: Description
    :type sender: Sender
    :param reporter: Description
    :type reporter: Reporter
    :param rate: Description
    :type rate: float
    :param count: Description
    :type count: int
    :return: Description
    :rtype: RunStats
    """
    stats = RunStats()
    total_tasks = len(tasks) * count
    if not tasks:
        raise ValueError("No Tasks provided!")
    
    reporter.start_report(total_tasks)
    i = 0
    while True:
        item = tasks[i % len(tasks)]
        result = sender.send(item)

        stats.sent += 1
        if result.code_expected == result.code_got:
            stats.passed += 1
        else:
            stats.failed += 1
        
        reporter.report(item, result)

        if count != 0 and stats.sent >= total_tasks:
            break

        if rate > 0:
            sleep(rate)

        i += 1
    
    return stats