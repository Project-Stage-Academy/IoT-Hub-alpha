import json
from typing import Any
from time import sleep, monotonic
from dataclasses import dataclass, asdict
from confluent_kafka import TopicPartition, Message
from django.conf import settings
from django.db import transaction
from apps.telemetry.models import Telemetry
from apps.devices.models import Device
from apps.telemetry.tasks import bulk_telemetry_write

    
@dataclass
class BufferedItem:
    kafka_msg: Message
    payload: dict[str, Any]
    device_serial: str


class WriteBuffer:
    def __init__(self, consumer, timeout):
        self.consumer = consumer
        self.timeout = timeout
        self.flush_ms = settings.DB_WRITER_LATENTCY_MS
        self.batch_size = settings.DB_WRITER_BATCH_SIZE
        self.max_buffer_size = settings.DB_WRITER_MAX_BUFFER_SIZE
        self.max_retry = settings.DB_WRITER_MAX_FLUSH_ATTEMPTS
        self.paused = False
        self.last_flush = monotonic()
        self.resume_threshold = int(self.max_buffer_size * 0.7)
        self.safety_sleep = settings.DB_WRITER_SAFETY_SAFE_SLEEP
        self.buffer = []

    def handle(self):

        while self.buffer_len > self.max_buffer_size:
            self._overflow_policy()

        message = self.consumer.poll(self.timeout)
              
        if not message:
            self._maybe_flush()
            return
        data = json.loads(message.value().decode("utf-8"))
        self.buffer.append(BufferedItem(kafka_msg=message, payload=data.get('payload'), device_serial=data.get('serial_number')))
        self._maybe_flush()

    def _flush(self, retry_num: int = 0) -> None:
        """
        Flush handlers, attempts write retries
        and sends payload to self._bulk_write_to_db
        send to DLQ topic upon X num failures
        
        :param self: Description
        :param retry_num: Description
        :param flush: Description
        """
        if not self.buffer:
            self.last_flush = monotonic()
            return
        
        flush = self.buffer[:self.batch_size]
        flush_serialized = [{"payload": p.payload, "device_serial": p.device_serial} for p in flush]
        print("Sending to worker")
        bulk_telemetry_write.delay(flush_serialized)
        self.last_flush = monotonic()
        
        self.buffer = self.buffer[self.batch_size:]
           
        self._commit_batch(flush)
        
        
        
    def _commit_batch(self, flush: list[BufferedItem]) -> None:
        """
        Commits the latest proccessed msg to kafka
        
        :param self: Description
        :param flush: Description
        :type flush: list[BufferedItem]
        """
        latest = {}
        for item in flush:
            m = item.kafka_msg
            k = (m.topic(), m.partition())
            latest[k] = max(latest.get(k, -1), m.offset())
            
        offsets = [TopicPartition(t, p, off + 1) for (t, p), off in latest.items()]
        self.consumer.commit(offsets=offsets, asynchronous=False)
      
    def _bulk_write_to_db(self, flush: list[BufferedItem]):
        """
        Generates Telem objects from payloads
        and writes them in bulk to DB
        
        :param self: Description
        :param flush: Description
        :type flush: list[BufferedItem]
        """
        serials = {p.device_serial for p in flush}
        device_by_serial = Device.objects.in_bulk(serials, field_name="serial_number")
        
        telem_data = []
        for p in flush:
            d = device_by_serial.get(p.device_serial)
            if not d:
                raise KeyError(f"Device not in DB: {d}")
            telem_data.append(Telemetry(payload=p.payload, device_id=d.id))
        
        with transaction.atomic():
            Telemetry.objects.bulk_create(telem_data, batch_size=self.batch_size)
    
    def _maybe_flush(self):
        time_check = (monotonic() - self.last_flush) * 1000 >= self.flush_ms
        size_check = self.buffer_len >= self.batch_size
        if time_check or size_check:
            self._flush()
    
    def _overflow_policy(self):
        self._pause()
        self._flush()
    
        if self.buffer_len >= self.max_buffer_size:
            sleep(self.safety_sleep)
        
        if self.buffer_len <= self.resume_threshold:
            self._resume()
    
    @property
    def buffer_len(self) -> int:
        return len(self.buffer)
        
    def _pause(self):
        if self.paused:
            return
        assigment = self.consumer.assignment()
        if assigment:
            self.consumer.pause(assigment)
            self.paused = True
            
    def _resume(self):
        if not self.paused:
            return
        assigment = self.consumer.assignment()
        if assigment:
            self.consumer.resume(assigment)
        self.paused = False

    def close(self):
        self.consumer.close()