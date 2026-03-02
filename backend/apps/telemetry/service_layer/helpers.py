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


def dump_jsonl(record: list[BufferedItem] | BufferedItem, reason, task_id="unknown"):
    path = Path(f"failed_telemetry/{task_id}.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.error(f"Dumping to JSONL at {path}")

    if not isinstance(record, list):
        record = [record]

    with path.open("a", encoding="utf-8") as f:
        for rec in record:
            normalized = {
                "payload": rec.payload,
                "device_serial": rec.device_serial,
                "failure_time": now().isoformat(),
                "reason": reason,
            }
            try:
                f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            except Exception:
                logger.error("JsonL dump failed!", extra={"normalized": normalized})


def safe_decode(v) -> str | None:
    if v is None:
        return None

    if isinstance(v, str):
        return v

    if isinstance(v, (bytes, bytearray, memoryview)):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return repr(v)

    return str(v)
