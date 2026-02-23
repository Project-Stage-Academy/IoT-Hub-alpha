import base64
import json
import logging
import os
import signal
import socket
import time
from datetime import timezone as dt_timezone
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from apps.telemetry.service_layer.write_buffer import WriteBuffer
from apps.telemetry.services import TelemetryValidator

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Consumer, KafkaError, Producer
except ImportError:  # pragma: no cover - depends on runtime environment
    Consumer = None  # type: ignore[assignment]
    Producer = None  # type: ignore[assignment]
    KafkaError = None  # type: ignore[assignment]


class RawContractError(Exception):
    """Raised when telemetry.raw message contract is invalid."""

    def __init__(self, code: str, detail: Any):
        super().__init__(str(detail))
        self.code = code
        self.detail = detail


class Command(BaseCommand):
    help = (
        "Consume telemetry.raw, validate + normalize payload, route to telemetry.clean "
        "or telemetry.dlq, and commit raw offset only after successful publish."
    )

    def __init__(self):
        super().__init__()
        self._running = True

    def add_arguments(self, parser):
        parser.add_argument(
            "--raw-topic",
            default=settings.KAFKA_TOPIC_TELEMETRY_RAW,
            help=f"Source topic (default: {settings.KAFKA_TOPIC_TELEMETRY_RAW})",
        )
        parser.add_argument(
            "--clean-topic",
            default=settings.KAFKA_TOPIC_TELEMETRY_CLEAN,
            help=f"Clean topic (default: {settings.KAFKA_TOPIC_TELEMETRY_CLEAN})",
        )
        parser.add_argument(
            "--dlq-topic",
            default=settings.KAFKA_TOPIC_TELEMETRY_DLQ,
            help=f"DLQ topic (default: {settings.KAFKA_TOPIC_TELEMETRY_DLQ})",
        )
        parser.add_argument(
            "--group-id",
            default=f"{settings.KAFKA_CLIENT_ID}-db-writer-stub",
            help="Kafka consumer group id",
        )
        parser.add_argument(
            "--poll-timeout",
            type=float,
            default=1.0,
            help="Consumer poll timeout in seconds (default: 1.0)",
        )
        parser.add_argument(
            "--max-messages",
            type=int,
            default=0,
            help="Stop after N routed messages (0 = run forever)",
        )

    def handle(self, *args, **options):
        if Consumer is None or Producer is None:
            raise CommandError(
                "confluent-kafka dependency is not installed. "
                "Install requirements to use kafka_db_writer_stub."
            )

        raw_topic = options["raw_topic"]
        clean_topic = options["clean_topic"]
        dlq_topic = options["dlq_topic"]
        group_id = options["group_id"]
        poll_timeout = options["poll_timeout"]
        max_messages = options["max_messages"]

        raw_consumer = Consumer(self._build_consumer_config(group_id))
        clean_consumer = Consumer(
            self._build_consumer_config(group_id="db-writer-clean")
        )
        producer = Producer(settings.KAFKA_PRODUCER_CONFIG)

        self._install_signal_handlers()
        raw_consumer.subscribe([raw_topic])
        clean_consumer.subscribe([clean_topic])

        write_buffer = WriteBuffer(clean_consumer, poll_timeout)

        self.stdout.write(
            self.style.SUCCESS(
                f"kafka_db_writer_stub started: raw={raw_topic}, clean={clean_topic}, "
                f"dlq={dlq_topic}, group={group_id}, auto_commit=false"
            )
        )

        processed = 0
        clean_count = 0
        dlq_count = 0
        publish_timeout = max(settings.KAFKA_REQUEST_TIMEOUT_MS / 1000.0, 1.0)

        try:
            while self._running:
                write_buffer.handle()
                message = raw_consumer.poll(poll_timeout)
                if message is None:
                    continue

                if message.error():
                    if (
                        KafkaError is not None
                        and message.error().code() == KafkaError._PARTITION_EOF
                    ):
                        continue

                    logger.error(
                        "kafka_db_writer_stub.consume_error",
                        extra={"error": str(message.error())},
                    )
                    continue

                routed = self._build_routed_message(
                    message=message,
                    clean_topic=clean_topic,
                    dlq_topic=dlq_topic,
                )

                source_key_text = self._decode_key_for_logs(message.key())
                try:
                    self._publish_envelope(
                        producer=producer,
                        topic=routed["target_topic"],
                        key=routed["key"],
                        envelope=routed["envelope"],
                        timeout_seconds=publish_timeout,
                    )
                    raw_consumer.commit(message=message, asynchronous=False)
                except Exception as exc:
                    logger.exception(
                        "kafka_db_writer_stub.route_failed",
                        extra={
                            "topic": message.topic(),
                            "partition": message.partition(),
                            "offset": message.offset(),
                            "key": source_key_text,
                            "event_id": routed["event_id"],
                            "target_topic": routed["target_topic"],
                            "error": str(exc),
                        },
                    )
                    raise CommandError(
                        "Failed to route message to clean/dlq and commit raw offset. "
                        "Stopping stub to preserve at-least-once behavior."
                    ) from exc

                processed += 1
                if routed["target_topic"] == clean_topic:
                    clean_count += 1
                else:
                    dlq_count += 1

                logger.info(
                    "kafka_db_writer_stub.routed",
                    extra={
                        "topic": message.topic(),
                        "partition": message.partition(),
                        "offset": message.offset(),
                        "key": source_key_text,
                        "event_id": routed["event_id"],
                        "target_topic": routed["target_topic"],
                    },
                )

                if max_messages > 0 and processed >= max_messages:
                    break
        finally:
            producer.flush(publish_timeout)
            raw_consumer.close()
            write_buffer.close()
            self.stdout.write(
                self.style.SUCCESS(
                    f"kafka_db_writer stopped: processed={processed}, "
                    f"clean={clean_count}, dlq={dlq_count}"
                )
            )

    def _build_consumer_config(self, group_id: str) -> dict[str, Any]:
        config = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": (
                f"{settings.KAFKA_CLIENT_ID}-db-writer-stub-"
                f"{socket.gethostname()}-{os.getpid()}"
            ),
            "group.id": group_id,
            "security.protocol": settings.KAFKA_SECURITY_PROTOCOL,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }

        if settings.KAFKA_SASL_MECHANISM:
            config["sasl.mechanism"] = settings.KAFKA_SASL_MECHANISM
        if settings.KAFKA_SASL_USERNAME:
            config["sasl.username"] = settings.KAFKA_SASL_USERNAME
        if settings.KAFKA_SASL_PASSWORD:
            config["sasl.password"] = settings.KAFKA_SASL_PASSWORD

        return config

    def _install_signal_handlers(self) -> None:
        def _stop(signum, frame):
            logger.info(
                "kafka_db_writer_stub.shutdown_signal",
                extra={"signal": signum},
            )
            self._running = False

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

    def _build_routed_message(
        self,
        *,
        message,
        clean_topic: str,
        dlq_topic: str,
    ) -> dict[str, Any]:
        source_topic = message.topic()
        source_partition = message.partition()
        source_offset = message.offset()
        source_key = message.key()

        raw_obj: Any | None = None
        raw_payload_for_dlq = self._decode_raw_for_dlq(message.value())

        try:
            raw_obj = self._decode_message_value(message.value())
            raw_payload_for_dlq = raw_obj
            contract = self._validate_raw_contract(raw_obj)
            normalized = self._normalize_payload(contract)

            event_id = self._build_event_id(
                raw_obj,
                source_topic=source_topic,
                source_partition=source_partition,
                source_offset=source_offset,
            )
            clean_key = source_key or contract["serial_number"].encode("utf-8")

            clean_envelope = {
                "event_id": event_id,
                "request_id": contract["request_id"],
                "ingest_protocol": contract["ingest_protocol"],
                "serial_number": contract["serial_number"],
                "ingest_index": contract["ingest_index"],
                "received_at": contract["received_at"],
                "processed_at": timezone.now().isoformat(),
                "device_id": normalized["device_id"],
                "payload": normalized["payload"],
            }
            if normalized.get("timestamp"):
                clean_envelope["timestamp"] = normalized["timestamp"]

            return {
                "event_id": event_id,
                "target_topic": clean_topic,
                "key": clean_key,
                "envelope": clean_envelope,
            }
        except RawContractError as exc:
            error_code = exc.code
            error_detail = exc.detail
        except Exception as exc:  # pragma: no cover - defensive fallback
            error_code = "unexpected_error"
            error_detail = str(exc)

        event_id = self._build_event_id(
            raw_obj,
            source_topic=source_topic,
            source_partition=source_partition,
            source_offset=source_offset,
        )
        dlq_key = self._resolve_dlq_key(source_key=source_key, raw_obj=raw_obj)
        dlq_envelope = {
            "event_id": event_id,
            "failed_at": timezone.now().isoformat(),
            "error": {
                "code": error_code,
                "detail": self._ensure_jsonable(error_detail),
            },
            "source": {
                "topic": source_topic,
                "partition": source_partition,
                "offset": source_offset,
                "key": self._decode_key_for_logs(source_key),
            },
            "raw_message": raw_payload_for_dlq,
        }

        return {
            "event_id": event_id,
            "target_topic": dlq_topic,
            "key": dlq_key,
            "envelope": dlq_envelope,
        }

    def _decode_message_value(self, raw_bytes: bytes | None) -> dict[str, Any]:
        if raw_bytes is None:
            raise RawContractError("empty_payload", "Message payload is empty")

        try:
            parsed = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RawContractError("malformed_json", str(exc)) from exc

        if not isinstance(parsed, dict):
            raise RawContractError(
                "invalid_contract",
                "Message payload must be a JSON object",
            )
        return parsed

    def _validate_raw_contract(self, raw_obj: dict[str, Any]) -> dict[str, Any]:
        required_fields = [
            "request_id",
            "ingest_protocol",
            "serial_number",
            "payload",
            "received_at",
            "ingest_index",
        ]
        missing = [field for field in required_fields if field not in raw_obj]
        if missing:
            raise RawContractError("missing_fields", {"missing": missing})

        request_id = raw_obj["request_id"]
        if not isinstance(request_id, str) or not request_id.strip():
            raise RawContractError(
                "invalid_request_id",
                "request_id must be non-empty",
            )
        try:
            UUID(request_id)
        except ValueError as exc:
            raise RawContractError("invalid_request_id", str(exc)) from exc

        ingest_protocol = raw_obj["ingest_protocol"]
        if not isinstance(ingest_protocol, str) or not ingest_protocol.strip():
            raise RawContractError(
                "invalid_ingest_protocol",
                "ingest_protocol must be non-empty",
            )

        serial_number = raw_obj["serial_number"]
        if not isinstance(serial_number, str) or not serial_number.strip():
            raise RawContractError(
                "invalid_serial_number",
                "serial_number must be non-empty",
            )

        payload = raw_obj["payload"]
        if not isinstance(payload, dict):
            raise RawContractError("invalid_payload", "payload must be a JSON object")

        payload_serial = payload.get("serial_number")
        if payload_serial and payload_serial != serial_number:
            raise RawContractError(
                "payload_serial_mismatch",
                "payload.serial_number must match top-level serial_number",
            )

        received_at_raw = raw_obj["received_at"]
        if not isinstance(received_at_raw, str):
            raise RawContractError(
                "invalid_received_at",
                "received_at must be string",
            )
        received_at_dt = parse_datetime(received_at_raw)
        if received_at_dt is None:
            raise RawContractError(
                "invalid_received_at",
                "received_at must be ISO 8601 datetime string",
            )
        received_at_dt = self._to_utc(received_at_dt)

        ingest_index = raw_obj["ingest_index"]
        if isinstance(ingest_index, bool) or not isinstance(ingest_index, int):
            raise RawContractError(
                "invalid_ingest_index",
                "ingest_index must be int",
            )
        if ingest_index < 0:
            raise RawContractError(
                "invalid_ingest_index",
                "ingest_index must be >= 0",
            )

        return {
            "request_id": request_id,
            "ingest_protocol": ingest_protocol,
            "serial_number": serial_number,
            "payload": payload,
            "received_at": received_at_dt.isoformat(),
            "ingest_index": ingest_index,
        }

    def _normalize_payload(self, contract: dict[str, Any]) -> dict[str, Any]:
        payload_input = dict(contract["payload"])
        payload_input["serial_number"] = contract["serial_number"]

        validated, error = TelemetryValidator.validate_single(payload_input)
        if error:
            raise RawContractError("payload_validation_failed", error)

        normalized = {
            "device_id": str(validated["device"].id),
            "payload": validated["payload"],
        }
        if validated.get("timestamp") is not None:
            normalized["timestamp"] = self._to_utc(validated["timestamp"]).isoformat()
        return normalized

    def _build_event_id(
        self,
        raw_obj: Any | None,
        *,
        source_topic: str,
        source_partition: int,
        source_offset: int,
    ) -> str:
        if isinstance(raw_obj, dict):
            request_id = raw_obj.get("request_id")
            ingest_index = raw_obj.get("ingest_index")
            if isinstance(request_id, str) and isinstance(ingest_index, int):
                return f"{request_id}:{ingest_index}"
        return f"{source_topic}:{source_partition}:{source_offset}"

    def _resolve_dlq_key(self, *, source_key: bytes | None, raw_obj: Any | None):
        if source_key is not None:
            return source_key

        if isinstance(raw_obj, dict):
            serial_number = raw_obj.get("serial_number")
            if isinstance(serial_number, str) and serial_number.strip():
                return serial_number.encode("utf-8")

        return None

    def _decode_key_for_logs(self, key: bytes | None) -> str | None:
        if key is None:
            return None

        try:
            return key.decode("utf-8")
        except UnicodeDecodeError:
            return key.hex()

    def _decode_raw_for_dlq(self, raw_bytes: bytes | None) -> Any:
        if raw_bytes is None:
            return None

        try:
            payload_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return {
                "encoding": "base64",
                "data": base64.b64encode(raw_bytes).decode("ascii"),
            }

        try:
            return json.loads(payload_text)
        except json.JSONDecodeError:
            return payload_text

    def _to_utc(self, value):
        if timezone.is_naive(value):
            return timezone.make_aware(value, dt_timezone.utc)
        return value.astimezone(dt_timezone.utc)

    def _ensure_jsonable(self, value: Any) -> Any:
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except (TypeError, ValueError):
            return str(value)

    def _publish_envelope(
        self,
        *,
        producer,
        topic: str,
        key: bytes | None,
        envelope: dict[str, Any],
        timeout_seconds: float,
    ) -> None:
        payload = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        delivery_status: dict[str, Any] = {"done": False, "error": None}
        started_at = time.monotonic()

        def _on_delivery(err, _msg) -> None:
            if err is not None:
                delivery_status["error"] = str(err)
            delivery_status["done"] = True

        retries_left = 3
        while True:
            try:
                producer.produce(
                    topic,
                    key=key,
                    value=payload,
                    on_delivery=_on_delivery,
                )
                producer.poll(0)
                break
            except BufferError:
                if retries_left == 0:
                    raise
                retries_left -= 1
                producer.poll(0.1)

        while not delivery_status["done"]:
            if time.monotonic() - started_at > timeout_seconds:
                raise RuntimeError(
                    f"Delivery callback timeout for topic '{topic}' after "
                    f"{timeout_seconds} seconds"
                )
            producer.poll(0.05)

        if delivery_status["error"]:
            raise RuntimeError(str(delivery_status["error"]))
