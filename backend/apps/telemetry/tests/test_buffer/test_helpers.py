from pathlib import Path


def test_get_producer_singleton_registers_flush(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.helpers as helpers

    created = {"n": 0}
    registered = {"fn": None}

    class DummyProducer:
        def __init__(self, cfg):
            created["n"] += 1
            self.cfg = cfg
            self.flush_calls = 0

        def flush(self, t):
            self.flush_calls += 1
            return 0

    monkeypatch.setattr(helpers, "settings", fake_settings)
    monkeypatch.setattr(helpers, "Producer", DummyProducer)

    def fake_register(fn):
        registered["fn"] = fn

    monkeypatch.setattr(helpers.atexit, "register", fake_register)

    p1 = helpers.get_producer()
    p2 = helpers.get_producer()

    assert p1 is p2
    assert created["n"] == 1
    assert registered["fn"] is not None

    registered["fn"]()
    assert p1.flush_calls == 1


def test_dump_jsonl_writes_buffereditem(monkeypatch, tmp_path):
    import apps.telemetry.service_layer.helpers as helpers
    from apps.telemetry.service_layer.data_structure import BufferedItem

    class DummyMsg: ...

    item = BufferedItem(kafka_msg=DummyMsg(), payload={"x": 1}, device_serial="ABC")

    monkeypatch.chdir(tmp_path)

    helpers.dump_jsonl(item, "reason-1", task_id="t1")
    out = Path("failed_telemetry/t1.jsonl")
    assert out.exists()

    txt = out.read_text("utf-8")
    assert '"device_serial": "ABC"' in txt
    assert '"reason": "reason-1"' in txt
    assert '"payload": {"x": 1}' in txt


def test_dump_jsonl_writes_list(monkeypatch, tmp_path):
    import apps.telemetry.service_layer.helpers as helpers
    from apps.telemetry.service_layer.data_structure import BufferedItem

    class DummyMsg: ...

    items = [
        BufferedItem(kafka_msg=DummyMsg(), payload={"x": 1}, device_serial="A"),
        BufferedItem(kafka_msg=DummyMsg(), payload={"x": 2}, device_serial="B"),
    ]

    monkeypatch.chdir(tmp_path)

    helpers.dump_jsonl(items, "multi", task_id="t2")
    out = Path("failed_telemetry/t2.jsonl")
    lines = out.read_text("utf-8").splitlines()
    assert len(lines) == 2
    assert '"device_serial": "A"' in lines[0]
    assert '"device_serial": "B"' in lines[1]
