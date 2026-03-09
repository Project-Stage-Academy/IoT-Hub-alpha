from confluent_kafka import Producer
from django.conf import settings
import threading

_producer = None
_lock = threading.Lock()


def get_kafka_producer() -> Producer:
    global _producer

    if _producer is None:
        with _lock:
            if _producer is None:
                _producer = Producer(settings.KAFKA_PRODUCER_CONFIG)

    return _producer
