from typing import Any
from dataclasses import dataclass
from confluent_kafka import TopicPartition, Message


@dataclass
class BufferedItem:
    kafka_msg: Message
    payload: dict[str, Any]
    device_serial: str


@dataclass
class InFlight:
    flush: list[BufferedItem]
    offsets: list[TopicPartition]
    start: float
