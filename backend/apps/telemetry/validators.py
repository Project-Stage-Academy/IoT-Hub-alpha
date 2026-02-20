from typing import Any
from uuid import UUID
from django.utils.dateparse import parse_datetime
from jsonschema import validate, ValidationError

from apps.telemetry.exceptions import RawContractError

ENVELOPE_SCHEMA = {
    "type": "object",
    "properties": {
        "request_id": {"type": "string", "minLength": 1},
        "ingest_protocol": {"type": "string", "minLength": 1},
        "serial_number": {"type": "string", "minLength": 1},
        "payload": {"type": "object"},
        "received_at": {"type": "string", "format": "date-time"},
        "ingest_index": {"type": "integer", "minimum": 0},
    },
    "required": [
        "request_id",
        "ingest_protocol",
        "serial_number",
        "payload",
        "received_at",
        "ingest_index",
    ],
}


def validate_raw_contract(raw_obj: dict[str, Any], to_utc_func) -> dict[str, Any]:
    """Checks the external contract of the message from Kafka."""
    try:
        validate(instance=raw_obj, schema=ENVELOPE_SCHEMA)
    except ValidationError as e:
        error_field = e.json_path.replace("$.", "") if e.json_path != "$" else "root"
        raise RawContractError(
            "invalid_contract", f"Schema error at '{error_field}': {e.message}"
        )

    request_id = raw_obj["request_id"]
    try:
        UUID(request_id)
    except ValueError as exc:
        raise RawContractError("invalid_request_id", str(exc)) from exc

    serial_number = raw_obj["serial_number"]
    payload = raw_obj["payload"]

    payload_serial = payload.get("serial_number")
    if payload_serial and payload_serial != serial_number:
        raise RawContractError(
            "payload_serial_mismatch",
            "payload.serial_number must match top-level serial_number",
        )

    received_at_dt = parse_datetime(raw_obj["received_at"])
    if received_at_dt is None:
        raise RawContractError(
            "invalid_received_at", "received_at must be ISO 8601 datetime string"
        )

    received_at_dt = to_utc_func(received_at_dt)

    return {
        "request_id": request_id,
        "ingest_protocol": raw_obj["ingest_protocol"],
        "serial_number": serial_number,
        "payload": payload,
        "received_at": received_at_dt.isoformat(),
        "ingest_index": raw_obj["ingest_index"],
    }
