import json
import logging
from celery.result import AsyncResult
from time import sleep, monotonic
from confluent_kafka import TopicPartition
from django.conf import settings
from apps.telemetry.tasks import bulk_telemetry_write
from apps.telemetry.service_layer.helpers import dump_jsonl
from apps.telemetry.service_layer.publish_to_dlq import publish_flush_to_dlq
from apps.telemetry.service_layer.data_structure import BufferedItem, InFlight
from config.metrics import BUFFER_FILL_RATIO



class WriteBuffer:
    def __init__(self, consumer, timeout):
        self.consumer = consumer
        self.timeout = timeout
        self.flush_ms = settings.DB_WRITER_LATENCY_MS
        self.batch_size = settings.DB_WRITER_BATCH_SIZE
        self.max_buffer_size = settings.DB_WRITER_MAX_BUFFER_SIZE
        self.max_retry = settings.DB_WRITER_MAX_FLUSH_ATTEMPTS
        self.paused = False
        self.last_flush = monotonic()
        self.last_celery_check = monotonic()
        self.resume_threshold = int(self.max_buffer_size * 0.7)
        self.safety_sleep = settings.DB_WRITER_SAFETY_SLEEP
        self.buffer = []
        self.inflight: dict[str, InFlight] = {}
        self.logger = logging.getLogger(__name__)

    def handle(self):
        if self.max_buffer_size > 0:
            BUFFER_FILL_RATIO.labels(component="db_writer_buffer").set(
                min(float(self.buffer_len) / float(self.max_buffer_size), 1.0)
            )
            
        while self.buffer_len > self.max_buffer_size:

            self.logger.warning(
                "Buffer overflow", extra={"buffer_size": self.buffer_len}
            )

            self._overflow_policy()

        task_time_check = (monotonic() - self.last_celery_check) * 1000 >= self.flush_ms
        if task_time_check:
            for task_id in list(self.inflight.keys()):
                self._check_celery_status(task_id)
            self.last_celery_check = monotonic()

        if not self.paused:
            message = self.consumer.consume(
                max(0, self.batch_size - self.buffer_len), self.timeout
            )

        for msg in message:

            if not msg:
                continue

            if msg.error():
                self.logger.warning(
                    "Bad message with error", extra={"error": msg.error(), "msg": msg}
                )
                continue

            data = json.loads(msg.value().decode("utf-8"))
            self.buffer.append(
                BufferedItem(
                    kafka_msg=msg,
                    payload=data.get("payload"),
                    device_serial=data.get("serial_number"),
                )
            )

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

        flush = self.buffer[: self.batch_size]
        flush_serialized = [
            {"payload": p.payload, "device_serial": p.device_serial} for p in flush
        ]
        self.logger.info(
            "Attempting flush", extra={"flush_size": len(flush_serialized)}
        )

        task = bulk_telemetry_write.delay(flush_serialized)

        if not task.id:
            dump_jsonl(flush, "Celery appeared offline")
            self._pause()
            return

        self.inflight[task.id] = InFlight(
            flush=flush, offsets=self._prepare_commit(flush), start=monotonic()
        )

        self.buffer = self.buffer[self.batch_size :]

        self.last_flush = monotonic()

    def _check_celery_status(self, task_id) -> None:
        res = AsyncResult(task_id)

        timed_out = False

        if (
            monotonic() - self.inflight[task_id].start
            > settings.DB_WRITER_CELERY_TIMEOUT_MIN * 60
        ):
            timed_out = True
        if not res.ready() and not timed_out:
            return

        data = res.result
        if data:
            success = data.get("success")
            written_db = data.get("written_to_db")
            written_dlq = data.get("written_to_dlq")
            if success:
                committed = self._commit_batch(task_id)
                if committed:
                    del self.inflight[task_id]
                return

            else:
                self.logger.error(
                    "celery task failed, dumping to jsonl",
                    extra={
                        "success": success,
                        "written_db": written_db,
                        "written_dlq": written_dlq,
                        "task_id": task_id,
                    },
                )
                dump_jsonl(
                    self.inflight[task_id].flush, "Failed DB and DLQ write", task_id
                )
                del self.inflight[task_id]
                self._pause()
        elif timed_out:
            self.logger.error("celery task timedout, dumping to jsonl")
            dump_jsonl(self.inflight[task_id].flush, "Failed DB and DLQ write", task_id)
            del self.inflight[task_id]
            self._pause()

    def _prepare_commit(self, flush: list[BufferedItem]) -> list[TopicPartition]:
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
            latest[k] = max(latest.get(k, -1), m.offset() or 0)

        return [TopicPartition(t, p, off + 1) for (t, p), off in latest.items()]

    def _commit_batch(self, id) -> bool:
        self.logger.info(
            "commiting offset", extra={"offset": self.inflight[id].offsets}
        )
        try:
            self.consumer.commit(offsets=self.inflight[id].offsets, asynchronous=False)
            return True
        except Exception as exc:
            self.logger.warning(
                "Offset commit failed, will retry",
                extra={"error": str(exc), "offsets": self.inflight[id].offsets},
            )
            return False

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

        self.logger.info("Polling of kafka paused")

    def _resume(self):
        if not self.paused:
            return
        assigment = self.consumer.assignment()
        if assigment:
            self.consumer.resume(assigment)
        self.paused = False

        self.logger.info("Polling of kafka resumed")

    def close(self):
        self.logger.info("DB Writer consumer closed.")
        self.consumer.close()
