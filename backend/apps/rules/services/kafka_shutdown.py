import atexit
from .kafka_inbound_singleton import get_kafka_producer


@atexit.register
def shutdown_kafka():
    producer = get_kafka_producer()
    producer.flush(10)
