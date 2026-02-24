import uuid
import pytest
from datetime import timezone

from apps.telemetry.validators import validate_raw_contract
from apps.telemetry.exceptions import RawContractError


@pytest.fixture
def mock_to_utc():
    """Fixture to mock UTC conversion."""
    return lambda dt: (
        dt.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None
        else dt.astimezone(timezone.utc)
    )


@pytest.fixture
def valid_payload():
    """
    Fixture returns a fresh valid payload for each test
    """

    return {
        "request_id": str(uuid.uuid4()),
        "ingest_protocol": "http",
        "serial_number": "SN-123",
        "payload": {
            "schema_version": "1.0",
            "serial_number": "SN-123",
            "value": 42,
        },
        "received_at": "2026-02-22T12:00:00Z",
        "ingest_index": 0,
    }


class TestValidateRawContract:

    def test_successful_validation(self, valid_payload, mock_to_utc):
        """Checks that a perfect contract passes without errors."""
        result = validate_raw_contract(valid_payload, mock_to_utc)

        assert result["request_id"] == valid_payload["request_id"]
        assert result["serial_number"] == "SN-123"
        assert result["ingest_index"] == 0

    def test_invalid_schema_missing_required_field(self, valid_payload, mock_to_utc):
        """Checks that missing required field in the contract raises an error."""
        del valid_payload["ingest_protocol"]

        with pytest.raises(RawContractError) as exc_info:
            validate_raw_contract(valid_payload, mock_to_utc)

        assert exc_info.value.code == "invalid_contract"
        assert "'ingest_protocol' is a required property" in exc_info.value.detail

    def test_invalid_uuid_request_id(self, valid_payload, mock_to_utc):
        """Checks that an invalid UUID for request_id is caught."""
        valid_payload["request_id"] = "not-a-valid-uuid"

        with pytest.raises(RawContractError) as exc_info:
            validate_raw_contract(valid_payload, mock_to_utc)

        assert exc_info.value.code == "invalid_request_id"

    def test_payload_serial_mismatch(self, valid_payload, mock_to_utc):
        """
        Checks that mismatched serial_number in contract
        and payload raises an error.
        """
        valid_payload["payload"] = {
            "schema_version": "1.0",
            "serial_number": "DIFFERENT-SN",
            "value": 42,
        }

        with pytest.raises(RawContractError) as exc_info:
            validate_raw_contract(valid_payload, mock_to_utc)

        assert exc_info.value.code == "payload_serial_mismatch"
        assert "must match top-level" in exc_info.value.detail

    def test_invalid_received_at_timestamp(self, valid_payload, mock_to_utc):
        """Checks that an invalid datetime format is rejected."""
        valid_payload["received_at"] = "not-a-datetime-string"

        with pytest.raises(RawContractError) as exc_info:
            validate_raw_contract(valid_payload, mock_to_utc)

        assert exc_info.value.code == "invalid_received_at"

    def test_payload_without_serial_number_passes(self, valid_payload, mock_to_utc):
        """
        Checks that validation passes successfully
        if payload doesn't contain serial_number.
        """
        valid_payload["payload"] = {"schema_version": "1.0", "value": 42}

        result = validate_raw_contract(valid_payload, mock_to_utc)
        assert result["serial_number"] == "SN-123"
