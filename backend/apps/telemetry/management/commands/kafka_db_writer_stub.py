import base64
import json
import logging
import os
import signal
import socket
import time
from datetime import timezone as dt_timezone
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.devices.models import Device
from apps.telemetry.services import process_telemetry_payload
from apps.telemetry.exceptions import RawContractError
from apps.telemetry.validators import validate_raw_contract
<<<<<<< HEAD
from apps.telemetry.service_layer.write_buffer import WriteBuffer
=======
>>>>>>> origin/main

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Consumer, KafkaError, Producer
except ImportError:
    Consumer, Producer, KafkaError = None, None, None


class Command(BaseCommand):
    help = "Consume telemetry.raw in BATCHES, validate, route, and publish."

    def __init__(self):
        super().__init__()
        self._running = True

    def add_arguments(self, parser):
        parser.add_argument("--raw-topic", default=settings.KAFKA_TOPIC_TELEMETRY_RAW)
        parser.add_argument(
            "--clean-topic", default=settings.KAFKA_TOPIC_TELEMETRY_CLEAN
        )
        parser.add_argument("--dlq-topic", default=settings.KAFKA_TOPIC_TELEMETRY_DLQ)
        parser.add_argument(
            "--group-id", default=f"{settings.KAFKA_CLIENT_ID}-db-writer-stub"
        )
        parser.add_argument("--poll-timeout", type=float, default=1.0)
        parser.add_argument("--max-messages", type=int, default=0)

        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of messages to process in one batch",
        )

    def handle(self, *args, **options):
        if Consumer is None:
            raise CommandError("confluent-kafka not installed.")

        raw_topic, clean_topic, dlq_topic = (
            options["raw_topic"],
            options["clean_topic"],
            options["dlq_topic"],
        )
        group_id, poll_timeout = options["group_id"], options["poll_timeout"]
        max_messages, batch_size = options["max_messages"], options["batch_size"]

        raw_consumer = Consumer(self._build_consumer_config(group_id))
        clean_consumer = Consumer(
            self._build_consumer_config(group_id="db-writer-clean")
        )
        producer = Producer(settings.KAFKA_PRODUCER_CONFIG)
        
        write_buffer = WriteBuffer(clean_consumer, poll_timeout)

        self._install_signal_handlers()
        raw_consumer.subscribe([raw_topic])
        clean_consumer.subscribe([clean_topic])

        self.stdout.write(
            self.style.SUCCESS(f"Worker started (BATCH SIZE: {batch_size})")
        )

        processed_total = 0
        publish_timeout = max(settings.KAFKA_REQUEST_TIMEOUT_MS / 1000.0, 5.0)

        try:
            while self._running:
                messages = raw_consumer.consume(
                    num_messages=batch_size, timeout=poll_timeout
                )

                if not messages:
                    continue

                batch_errors = []

                def _batch_delivery_callback(err, msg):
                    if err:
                        batch_errors.append(err)

                for message in messages:
                    if message.error():
                        if message.error().code() != KafkaError._PARTITION_EOF:
                            logger.error(
                                "kafka_consume_error",
                                extra={"error": str(message.error())},
                            )
                        continue

                    routed = self._build_routed_message(message, clean_topic, dlq_topic)
                    payload_bytes = json.dumps(
                        routed["envelope"], ensure_ascii=False
                    ).encode("utf-8")

                    max_retries = 3
                    for attempt in range(max_retries + 1):
                        try:
                            producer.produce(
                                topic=routed["target_topic"],
                                key=routed["key"],
                                value=payload_bytes,
                                on_delivery=_batch_delivery_callback,
                            )
                            producer.poll(0)
                            break
                        except BufferError:
                            if attempt == max_retries:
                                logger.critical(
                                    "Kafka producer buffer full. Max retries exceeded.",
                                    extra={"event_id": routed.get("event_id")},
                                )
                                raise CommandError(
                                    "Failed to publish message due to persistent "
                                    "BufferError. Stopping stub to preserve "
                                    "at-least-once behavior."
                                )

                            logger.warning(
                                "BufferError caught. Waiting for buffer to clear...",
                                extra={
                                    "attempt": attempt + 1,
                                    "max_retries": max_retries,
                                },
                            )
                            producer.poll(0.5)

                    processed_total += 1

                producer.flush(publish_timeout)

                write_buffer.handle()

                if batch_errors:
                    logger.critical(
                        f"Batch publish failed with {len(batch_errors)} errors."
                        f" First error: {batch_errors[0]}"
                    )
                    raise CommandError(
                        "Failed to route batch. Stopping stub to preserve "
                        "at-least-once behavior."
                    )
                raw_consumer.commit(asynchronous=False)

                logger.info(
                    "Successfully processed and committed batch "
                    f"of {len(messages)} messages."
                )

                if max_messages > 0 and processed_total >= max_messages:
                    break

        finally:
            producer.flush(publish_timeout)
            clean_consumer.close()
            raw_consumer.close()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Worker stopped. Total processed: {processed_total}"
                )
            )

    def _build_routed_message(
        self, message, clean_topic: str, dlq_topic: str
    ) -> dict[str, Any]:
        source_topic, source_partition, source_offset = (
            message.topic(),
            message.partition(),
            message.offset(),
        )
        source_key = message.key()

        raw_obj: Any | None = None
        raw_payload_for_dlq = self._decode_raw_for_dlq(message.value())

        try:
            raw_obj = self._decode_message_value(message.value())
            raw_payload_for_dlq = raw_obj

            contract = validate_raw_contract(raw_obj, self._to_utc)

            normalized = self._normalize_payload(contract)

            event_id = self._build_event_id(
                raw_obj, source_topic, source_partition, source_offset
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
            error_code, error_detail = exc.code, exc.detail
        except Exception as exc:
            error_code, error_detail = "unexpected_error", str(exc)

        event_id = self._build_event_id(
            raw_obj, source_topic, source_partition, source_offset
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

    def _normalize_payload(self, contract: dict[str, Any]) -> dict[str, Any]:
        payload_input = dict(contract["payload"])
        payload_input["serial_number"] = contract["serial_number"]

        clean_payload, error = process_telemetry_payload(payload_input)
        if error:
            raise RawContractError("payload_validation_failed", error)

        try:
            device = Device.objects.get(serial_number=contract["serial_number"])
        except Device.DoesNotExist:
            raise RawContractError(
                "unknown_device", f"Device SN: {contract['serial_number']} not found"
            )

        normalized = {"device_id": str(device.id), "payload": clean_payload}

        if (timestamp_val := clean_payload.get("timestamp")) is not None:
            normalized["timestamp"] = (
                timestamp_val
                if isinstance(timestamp_val, str)
                else self._to_utc(timestamp_val).isoformat()
            )

        return normalized

    def _build_consumer_config(self, group_id: str) -> dict[str, Any]:
        config = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "client.id": (
                f"{settings.KAFKA_CLIENT_ID}"
                f"-db-writer-stub-{socket.gethostname()}-{os.getpid()}"
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
            self._running = False

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

    def _decode_message_value(self, raw_bytes: bytes | None) -> dict[str, Any]:
        if raw_bytes is None:
            raise RawContractError("empty_payload", "Message payload is empty")
        try:
            parsed = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RawContractError("malformed_json", str(exc)) from exc
        if not isinstance(parsed, dict):
            raise RawContractError(
                "invalid_contract", "Message payload must be a JSON object"
            )
        return parsed

    def _build_event_id(self, raw_obj, source_topic, source_partition, source_offset):
        if isinstance(raw_obj, dict):
            if isinstance(req_id := raw_obj.get("request_id"), str) and isinstance(
                idx := raw_obj.get("ingest_index"), int
            ):
                return f"{req_id}:{idx}"
        return f"{source_topic}:{source_partition}:{source_offset}"

    def _resolve_dlq_key(self, source_key, raw_obj):
        if source_key is not None:
            return source_key
        if (
            isinstance(raw_obj, dict)
            and isinstance(sn := raw_obj.get("serial_number"), str)
            and sn.strip()
        ):
            return sn.encode("utf-8")
        return None

    def _decode_key_for_logs(self, key):
        if key is None:
            return None
        try:
            return key.decode("utf-8")
        except UnicodeDecodeError:
            return key.hex()

    def _decode_raw_for_dlq(self, raw_bytes):
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
            return {
                "encoding": "utf-8",
                "data": payload_text,
            }

    def _to_utc(self, value):
        if timezone.is_naive(value):
            return timezone.make_aware(value, dt_timezone.utc)
        return value.astimezone(dt_timezone.utc)

    def _ensure_jsonable(self, value):
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except (TypeError, ValueError):
            return str(value)
