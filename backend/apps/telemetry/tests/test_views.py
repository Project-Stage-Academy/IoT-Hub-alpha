import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _mock_producer():
    """Patch the producer so publish_raw is a no-op in all view tests."""
    with patch("apps.telemetry.views.get_producer") as mock_get:
        mock_get.return_value = MagicMock()
        yield mock_get.return_value


class TestTelemetryIngestView:
    """Tests for the publish-only HTTP ingestion endpoint."""

    def test_single_payload_accepted(self, client, device, _mock_producer):
        payload = {"schema_version": "1.0", "value": 2550}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 1
        _mock_producer.publish_raw.assert_called_once()

    def test_batch_payload_accepted(self, client, device, _mock_producer):
        payload = [
            {"schema_version": "1.0", "value": 100},
            {"schema_version": "1.0", "value": 200},
        ]

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["count"] == 2
        assert _mock_producer.publish_raw.call_count == 2

    def test_idempotency_key_returned(self, client, device):
        payload = {"schema_version": "1.0"}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
            HTTP_IDEMPOTENCY_KEY="test-key-123",
        )

        assert response.status_code == 202
        data = response.json()
        assert data["idempotency_key"] == "test-key-123"

    def test_missing_serial_number_header(self, client):
        payload = {"schema_version": "1.0"}

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.json()
        assert "X-Device-Serial-Number header is required" in data["error"]

    def test_invalid_json(self, client):
        response = client.post(
            "/api/v1/telemetry/",
            data="not valid json",
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid JSON payload" in data["error"]

    def test_empty_batch(self, client, device):
        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps([]),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        data = response.json()
        assert "Empty batch" in data["error"]

    def test_batch_exceeds_limit(self, client, device):
        payload = [{"schema_version": "1.0"}] * 1001

        response = client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        assert response.status_code == 400
        data = response.json()
        assert "exceeds maximum limit" in data["error"]

    def test_serial_number_injected_into_payload(self, client, device, _mock_producer):
        payload = {"value": 42}

        client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        call_kwargs = _mock_producer.publish_raw.call_args.kwargs
        assert call_kwargs["serial_number"] == device.serial_number
        assert call_kwargs["source"] == "http"

    def test_publish_raw_called_with_correct_source(
        self, client, device, _mock_producer
    ):
        payload = {"value": 1}

        client.post(
            "/api/v1/telemetry/",
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_DEVICE_SERIAL_NUMBER=device.serial_number,
        )

        call_kwargs = _mock_producer.publish_raw.call_args.kwargs
        assert call_kwargs["source"] == "http"
        assert "data" in call_kwargs
