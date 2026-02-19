from confluent_kafka import Producer
from django.conf import settings

_producer: Producer | None = None

def get_producer() -> Producer:
    global _producer
    if _producer is None:
        _producer = Producer(settings.KAFKA_PRODUCER_CONFIG)
    return _producer
