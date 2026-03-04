import pytest
import types


@pytest.fixture()
def fake_settings():
    # same as base.py conf.
    return types.SimpleNamespace(
        KAFKA_PRODUCER_CONFIG={"bootstrap.servers": "fake:9092"},
        KAFKA_TOPIC_TELEMETRY_DLQ="telem.dlq",
        DB_WRITER_LATENCY_MS=50,
        DB_WRITER_BATCH_SIZE=2,
        DB_WRITER_MAX_BUFFER_SIZE=10,
        DB_WRITER_MAX_FLUSH_ATTEMPTS=3,
        DB_WRITER_SAFETY_SLEEP=0.0,
        DB_WRITER_CELERY_TIMEOUT_MIN=1,
    )
