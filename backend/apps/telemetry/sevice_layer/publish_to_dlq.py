import json
from django.conf import settings

def publish_flush_to_dlq(producer, flush, *, reason: str) -> None:

    for p in flush:
        envelope = {
            "reason": reason,
            "device_serial": p.get('device_serial') or None,
            "payload": p.get('payload') or None,
        }

        payload_bytes = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        key_bytes = (p.get('device_serial') or "").encode("utf-8")

        while True:
            try:
                producer.produce(
                    settings.KAFKA_PIPELINE_TOPICS.KAFKA_TOPIC_TELEMETRY_DLQ,
                    key=key_bytes,
                    value=payload_bytes,
                    headers=[("dlq_reason", reason.encode("utf-8"))],
                )
                break
            except BufferError:
                producer.poll(0.2)

        producer.poll(0)

    remaining = producer.flush(10.0)
    if remaining:
        raise RuntimeError(f"DLQ publish not confirmed; {remaining} messages still undelivered")