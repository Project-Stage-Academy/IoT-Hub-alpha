import json
from django.conf import settings


def publish_flush_to_dlq(producer, flush, *, reason: str) -> bool:

    for p in flush:
        envelope = {
            "reason": reason,
            "device_serial": p.get("device_serial") or None,
            "payload": p.get("payload") or None,
        }

        payload_bytes = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        key_bytes = (p.get("device_serial") or "").encode("utf-8")

        for _ in range(50):
            try:
                producer.produce(
                    settings.KAFKA_TOPIC_TELEMETRY_DLQ,
                    key=key_bytes,
                    value=payload_bytes,
                    headers=[("dlq_reason", reason.encode("utf-8"))],
                )
                break
            except BufferError:
                producer.poll(0.2)
        else:
            return False

        producer.poll(0)

    remaining = producer.flush(10.0)
    if remaining:
        return False

    return True
