import json
from datetime import timezone
from django.conf import settings
from django.utils import timezone as tz
from .helpers import safe_decode


def publish_flush_to_dlq(
    producer, flush, *, reason: str, error_detail: str | None = None
) -> bool:
    failed_at = tz.now().astimezone(timezone.utc).isoformat()

    for p in flush:
        meta = p.get("meta") or {}
        raw_message = meta.get("raw_message") or {}
        source = meta.get("source") or {}
        request_id = raw_message.get("request_id")
        ingest_index = raw_message.get("ingest_index")
        payload = p.get("payload") or {}
        raw_message["payload"] = payload
        event_id = (
            f"{request_id}:{ingest_index}"
            if request_id is not None and ingest_index is not None
            else None
        )

        key_str = (
            safe_decode(source.get("key"))
            or raw_message.get("serial_number")
            or p.get("device_serial")
            or ""
        )

        envelope = {
            "event_id": event_id,
            "failed_at": failed_at,
            "error": {
                "code": reason,
                "detail": (p.get("error_detail") or error_detail or ""),
            },
            "source": source,
            "raw_message": raw_message,
        }

        payload_bytes = json.dumps(
            envelope, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        key_bytes = (key_str or "").encode("utf-8")

        for _ in range(50):
            try:
                producer.produce(
                    settings.KAFKA_TOPIC_TELEMETRY_DLQ,
                    key=key_bytes,
                    value=payload_bytes,
                    headers=[
                        ("dlq_reason", reason.encode("utf-8")),
                        ("event_id", (event_id or "").encode("utf-8")),
                    ],
                )
                break
            except BufferError:
                producer.poll(0.2)
        else:
            return False

        producer.poll(0)

    remaining = producer.flush(10.0)
    return remaining == 0
