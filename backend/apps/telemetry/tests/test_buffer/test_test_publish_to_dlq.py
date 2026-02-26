import json


def test_publish_flush_to_dlq_retries_then_success(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.publish_to_dlq as dlq

    monkeypatch.setattr(dlq, "settings", fake_settings)

    calls = {"produce": 0, "poll": 0, "flush": 0}

    class DummyProducer:
        def __init__(self):
            self.fail_left = 2

        def produce(self, topic, key, value, headers):
            calls["produce"] += 1
            if self.fail_left > 0:
                self.fail_left -= 1
                raise BufferError("full")

            assert topic == fake_settings.KAFKA_TOPIC_TELEMETRY_DLQ

            env = json.loads(value.decode("utf-8"))

            assert env["error"]["code"] == "R"
            assert "failed_at" in env
            assert "raw_message" in env
            assert "source" in env

            assert headers[0][0] == "dlq_reason"
            assert headers[0][1] == b"R"
            assert headers[1][0] == "event_id"

        def poll(self, t):
            calls["poll"] += 1

        def flush(self, t):
            calls["flush"] += 1
            return 0

    ok = dlq.publish_flush_to_dlq(
        DummyProducer(),
        [{"device_serial": "A", "payload": {"x": 1}}],
        reason="R",
    )
    assert ok is True
    assert calls["produce"] >= 3
    assert calls["flush"] == 1


def test_publish_flush_to_dlq_retry_exhausted_returns_false(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.publish_to_dlq as dlq

    monkeypatch.setattr(dlq, "settings", fake_settings)

    class DummyProducer:
        def produce(self, *a, **k):
            raise BufferError("full")

        def poll(self, t):
            pass

        def flush(self, t):
            return 0

    ok = dlq.publish_flush_to_dlq(
        DummyProducer(), [{"device_serial": "A", "payload": {"x": 1}}], reason="R"
    )
    assert ok is False


def test_publish_flush_to_dlq_flush_remaining_returns_false(monkeypatch, fake_settings):
    import apps.telemetry.service_layer.publish_to_dlq as dlq

    monkeypatch.setattr(dlq, "settings", fake_settings)

    class DummyProducer:
        def produce(self, *a, **k):
            pass

        def poll(self, t):
            pass

        def flush(self, t):
            return 1

    ok = dlq.publish_flush_to_dlq(
        DummyProducer(), [{"device_serial": "A", "payload": {"x": 1}}], reason="R"
    )
    assert ok is False
