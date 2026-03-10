import json
from confluent_kafka import KafkaError
from django.conf import settings
import logging
from .kafka_inbound_singleton import get_kafka_producer


class ProducerError(Exception):
    pass


class ExternalProducer:
    def __init__(self):
        self.producer = get_kafka_producer()
        self.output = settings.KAFKA_TOPIC_EVENT
        self.logger = logging.getLogger(__name__)

    def produce(self, data: dict):
        if not data:
            raise ProducerError("Empty rule")

        payload = json.dumps(data).encode("utf-8")

        try:
            self.producer.produce(
                topic=self.output,
                key=str(data.get("device_id")).encode("utf-8"),
                value=payload,
                on_delivery=self._delivery_callback,
            )

            self.producer.poll(0)

        except BufferError:
            self.producer.poll(0.5)
            raise ProducerError("Kafka producer queue full")

    def _delivery_callback(self, err: KafkaError | None, msg):
        if err:
            self.logger.error("Kafka delivery failed: %s", err)
