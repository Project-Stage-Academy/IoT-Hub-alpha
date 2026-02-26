import json


class DummyMessage:
    def __init__(self, value=b"{}", key=b"", topic="telemetry.clean", partition=0, offset=0):
        if isinstance(value, (dict, list)):
            value = json.dumps(value).encode("utf-8")
        elif isinstance(value, str):
            value = value.encode("utf-8")
        self._value = value
        self._key = key
        self._topic = topic
        self._partition = partition
        self._offset = offset
        self._err = None

    def value(self):
        return self._value

    def key(self):
        return self._key

    def error(self):
        return self._err

    def topic(self):
        return self._topic

    def partition(self):
        return self._partition

    def offset(self):
        return self._offset


class DummyConsumer:
    def __init__(self, messages):
        self._messages = list(messages)
        self.commit_calls = []
        self.paused = False
        self.pause_calls = 0
        self.resume_calls = 0
        self.poll_calls = 0
        
    def poll(self, timeout=0):
        self.poll_calls += 1
        return None

    def consume(self, n, timeout):
        out = self._messages[:n]
        self._messages = self._messages[n:]
        return out

    def assignment(self):
        return ["p0"]

    def pause(self, a):
        self.paused = True
        self.pause_calls += 1

    def resume(self, a):
        self.paused = False
        self.resume_calls += 1

    def commit(self, offsets=None, asynchronous=False):
        self.commit_calls.append((offsets, asynchronous))

    def close(self):
        pass


class DummyTopicPartition:
    def __init__(self, topic, partition, offset):
        self.topic = topic
        self.partition = partition
        self.offset = offset

    def __repr__(self):
        return f"TP({self.topic},{self.partition},{self.offset})"


def test_handle_consumes_and_flushes_to_inflight(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.write_buffer as wb

    monkeypatch.setattr(wb, "settings", fake_settings)
    monkeypatch.setattr(wb, "TopicPartition", DummyTopicPartition)

    class DummyTask:
        id = "tid1"

    monkeypatch.setattr(wb.bulk_telemetry_write, "delay", lambda payload: DummyTask())

    dumped = {"called": False}
    monkeypatch.setattr(
        wb, "dump_jsonl", lambda *a, **k: dumped.__setitem__("called", True)
    )

    consumer = DummyConsumer(
        [
            DummyMessage({"payload": {"x": 1}, "serial_number": "S1"}, offset=10),
            DummyMessage({"payload": {"x": 2}, "serial_number": "S2"}, offset=11),
        ]
    )

    buf = wb.WriteBuffer(consumer, timeout=0.01, batch_size=200)
    buf.batch_size = 2
    buf.flush_ms = 10_000

    buf.handle()

    assert dumped["called"] is False
    assert len(buf.inflight) == 1
    assert buf.buffer_len == 0


def test_flush_celery_offline_dumps_and_pauses(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.write_buffer as wb

    monkeypatch.setattr(wb, "settings", fake_settings)
    monkeypatch.setattr(wb, "TopicPartition", DummyTopicPartition)

    class DummyTask:
        id = None

    monkeypatch.setattr(wb.bulk_telemetry_write, "delay", lambda payload: DummyTask())

    dumped = {"called": False}
    monkeypatch.setattr(
        wb, "dump_jsonl", lambda *a, **k: dumped.__setitem__("called", True)
    )

    consumer = DummyConsumer(
        [DummyMessage({"payload": {"x": 1}, "serial_number": "S1"}, offset=5)]
    )
    buf = wb.WriteBuffer(consumer, timeout=0.01, batch_size=200)
    buf.batch_size = 1
    buf.flush_ms = 0

    buf.handle()

    assert dumped["called"] is True
    assert consumer.paused is True
    assert len(buf.inflight) == 0


def test_check_celery_success_commits(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.write_buffer as wb

    monkeypatch.setattr(wb, "settings", fake_settings)
    monkeypatch.setattr(wb, "TopicPartition", DummyTopicPartition)

    consumer = DummyConsumer([])
    buf = wb.WriteBuffer(consumer, timeout=0.01, batch_size=200)

    msg = DummyMessage({"payload": {"x": 1}, "serial_number": "S1"}, offset=10)
    item = wb.BufferedItem(kafka_msg=msg, payload={"x": 1}, device_serial="S1")
    buf.inflight["tidX"] = wb.InFlight(
        flush=[item],
        offsets=buf._prepare_commit([item]),
        start=0.0,
    )

    class FakeAsyncResult:
        def __init__(self, tid):
            self.result = {"success": True, "written_to_db": 1, "written_to_dlq": 0}

        def ready(self):
            return True

    monkeypatch.setattr(wb, "AsyncResult", FakeAsyncResult)

    buf._check_celery_status("tidX")

    assert consumer.commit_calls, "expected commit"
    offsets, async_flag = consumer.commit_calls[0]
    assert async_flag is False
    assert offsets[0].offset == 11
    assert "tidX" not in buf.inflight


def test_check_celery_success_false_dumps_and_pauses(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.write_buffer as wb

    monkeypatch.setattr(wb, "settings", fake_settings)
    monkeypatch.setattr(wb, "TopicPartition", DummyTopicPartition)

    consumer = DummyConsumer([])
    buf = wb.WriteBuffer(consumer, timeout=0.01, batch_size=200)

    msg = DummyMessage({"payload": {"x": 1}, "serial_number": "S1"}, offset=10)
    item = wb.BufferedItem(kafka_msg=msg, payload={"x": 1}, device_serial="S1")
    buf.inflight["tidBad"] = wb.InFlight(
        flush=[item], offsets=buf._prepare_commit([item]), start=0.0
    )

    dumped = {"called": False}
    monkeypatch.setattr(
        wb, "dump_jsonl", lambda *a, **k: dumped.__setitem__("called", True)
    )

    class FakeAsyncResult:
        def __init__(self, tid):
            self.result = {"success": False, "written_to_db": 0, "written_to_dlq": 0}

        def ready(self):
            return True

    monkeypatch.setattr(wb, "AsyncResult", FakeAsyncResult)

    buf._check_celery_status("tidBad")

    assert dumped["called"] is True
    assert consumer.paused is True
    assert "tidBad" not in buf.inflight


def test_check_celery_timeout_dumps_and_pauses(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.write_buffer as wb

    monkeypatch.setattr(wb, "settings", fake_settings)
    monkeypatch.setattr(wb, "TopicPartition", DummyTopicPartition)

    consumer = DummyConsumer([])
    buf = wb.WriteBuffer(consumer, timeout=0.01, batch_size=200)

    msg = DummyMessage({"payload": {"x": 1}, "serial_number": "S1"}, offset=10)
    item = wb.BufferedItem(kafka_msg=msg, payload={"x": 1}, device_serial="S1")

    buf.inflight["tidT"] = wb.InFlight(
        flush=[item], offsets=buf._prepare_commit([item]), start=-10_000.0
    )

    dumped = {"called": False}
    monkeypatch.setattr(
        wb, "dump_jsonl", lambda *a, **k: dumped.__setitem__("called", True)
    )

    class FakeAsyncResult:
        def __init__(self, tid):
            self.result = None

        def ready(self):
            return False

    monkeypatch.setattr(wb, "AsyncResult", FakeAsyncResult)

    buf._check_celery_status("tidT")

    assert dumped["called"] is True
    assert consumer.paused is True
    assert "tidT" not in buf.inflight
