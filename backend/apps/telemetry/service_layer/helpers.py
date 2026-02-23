import json
from pathlib import Path
import atexit
import logging
from typing import Any
from django.utils.timezone import now
from confluent_kafka import Producer
from django.conf import settings
from apps.telemetry.service_layer.data_structure import BufferedItem

_producer: Producer | None = None

logger = logging.getLogger(__name__)


def get_producer():
    global _producer
    if _producer is None:
        _producer = Producer(settings.KAFKA_PRODUCER_CONFIG)
        atexit.register(lambda: _producer.flush(5))
    return _producer


def dump_helper(path, rec, reason):
    normalized = {
        "payload": rec.payload,
        "device_serial": rec.device_serial,
        "failure_time": now().isoformat(),
        "reason": reason,
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(normalized, ensure_ascii=False) + "\n")


def dump_jsonl(record: list[BufferedItem] | BufferedItem, reason, task_id="unknown"):
    path = Path(f"failed_telemetry/{task_id}.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.error(f"Dumping to JSONL at {path}")
    if isinstance(record, list):
        for rec in record:
            dump_helper(path, rec, reason)
    else:
        dump_helper(path, record, reason)
